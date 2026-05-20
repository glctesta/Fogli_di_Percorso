"""Orchestrazione transazionale per la dichiarazione mensile (workflow DRAFT/SUBMITTED).

- create_draft_*: crea una bozza (Status=DRAFT, RegistryId=NULL). Niente SP.
- update_draft_*: modifica una bozza esistente. Sostituisce i documenti.
- submit: chiama SP Registro e marca SUBMITTED. Solo nella finestra 1-5 del mese successivo.
"""
from __future__ import annotations

from datetime import date
from typing import Callable, Optional, Sequence

from fdp_app.pathtracks.calculator import (
    compute_fuel_reimbursement,
    compute_taxi_reimbursement,
)
from fdp_app.pathtracks.deadline import (
    can_create_draft_for,
    can_submit_for,
)
from fdp_app.pathtracks.currency import (
    CurrencyService,
    RateNotResolvableError,
)
from fdp_app.repos.coordinate_repo import CoordinateRepo
from fdp_app.repos.doc_repo import PathTrackDocRepo
from fdp_app.repos.pathtrack_repo import PathTrackRepo
from fdp_app.repos.rate_repo import RateRepo
from fdp_app.repos.registry_repo import RegistryRepo


class NoActiveCoordinateError(Exception):
    """Nessun punto di partenza attivo per il dipendente."""


class NoRateConfiguredError(Exception):
    """Nessun rate configurato per la data."""


class DuplicateDeclarationError(Exception):
    """Esiste gia' una dichiarazione attiva (DRAFT o SUBMITTED) per lo stesso mese."""


class DeadlineClosedError(Exception):
    """Finestra temporale non aperta per l'azione richiesta."""


class InvalidInputError(Exception):
    """Input validato lato service rifiutato."""


class NotADraftError(Exception):
    """Tentativo di modificare/inviare un record non in stato DRAFT."""


class PathTrackService:
    def __init__(
        self,
        *,
        coordinate_repo: CoordinateRepo,
        rate_repo: RateRepo,
        registry_repo: RegistryRepo,
        pathtrack_repo: PathTrackRepo,
        doc_repo: PathTrackDocRepo,
        connection_factory: Callable[[], object],
        currency_service: Optional[CurrencyService] = None,
    ) -> None:
        self._coord_repo = coordinate_repo
        self._rate_repo = rate_repo
        self._registry_repo = registry_repo
        self._pathtrack_repo = pathtrack_repo
        self._doc_repo = doc_repo
        self._connection_factory = connection_factory
        self._currency_service = currency_service

    # ---- shared validation -----------------------------------------------

    def _validate_common(
        self,
        *,
        number_of_trips: int,
        sheet_pdf: Optional[bytes],
        receipt_pdfs: Sequence[bytes],
    ) -> None:
        if not (1 <= number_of_trips <= 31):
            raise InvalidInputError(
                f"viaggi: deve essere tra 1 e 31, ricevuto {number_of_trips}"
            )
        if not sheet_pdf or not sheet_pdf.startswith(b"%PDF-"):
            raise InvalidInputError(
                "foglio di percorso PDF obbligatorio e deve essere un PDF valido"
            )
        for i, pdf in enumerate(receipt_pdfs):
            if not pdf or not pdf.startswith(b"%PDF-"):
                raise InvalidInputError(f"ricevuta {i+1} non e' un PDF valido")

    def _insert_docs(
        self,
        *,
        path_track_id: int,
        sheet_pdf: bytes,
        receipt_pdfs: Sequence[bytes],
        sheet_title: str,
        receipt_title_prefix: str,
    ) -> None:
        self._doc_repo.insert(
            path_track_id=path_track_id,
            doc_title=sheet_title,
            pdf_bytes=sheet_pdf,
        )
        for i, pdf in enumerate(receipt_pdfs, start=1):
            self._doc_repo.insert(
                path_track_id=path_track_id,
                doc_title=f"{receipt_title_prefix} {i}",
                pdf_bytes=pdf,
            )

    # ---- create draft ----------------------------------------------------

    def create_draft_fuel(
        self,
        *,
        employee_hire_history_id: int,
        date_path_track: date,
        number_of_trips: int,
        sheet_pdf: Optional[bytes],
        receipt_pdfs: Sequence[bytes],
        in_behalf_of_id: Optional[int] = None,
    ) -> int:
        self._validate_common(
            number_of_trips=number_of_trips,
            sheet_pdf=sheet_pdf,
            receipt_pdfs=receipt_pdfs,
        )
        if not receipt_pdfs:
            raise InvalidInputError("almeno una ricevuta carburante obbligatoria")

        if not can_create_draft_for(date_path_track):
            raise DeadlineClosedError(
                f"Periodo di inserimento per {date_path_track:%Y-%m} non aperto"
            )

        target_employee_id = in_behalf_of_id or employee_hire_history_id

        coord = self._coord_repo.find_active(target_employee_id)
        if coord is None:
            raise NoActiveCoordinateError(
                f"Nessun punto di partenza attivo per dipendente {target_employee_id}"
            )

        rate = self._rate_repo.find_for_date(date_path_track)
        if rate is None:
            raise NoRateConfiguredError(
                f"Nessun rate configurato per {date_path_track}"
            )

        existing = self._pathtrack_repo.find_active_for_month(
            employee_hire_history_id=target_employee_id,
            date_path_track=date_path_track,
        )
        if existing is not None:
            raise DuplicateDeclarationError(
                f"Esiste gia' una dichiarazione attiva per {date_path_track}"
            )

        amount = compute_fuel_reimbursement(
            road_km_one_way=coord.road_km_to_workplace,
            number_of_trips=number_of_trips,
            avg_consumption_km_l=rate.avg_consumption_km_l,
            avg_fuel_price_eur_l=rate.avg_fuel_price_eur_l,
        )

        conn = self._connection_factory()
        prev_autocommit = getattr(conn, "autocommit", True)
        try:
            conn.autocommit = False
            new_id = self._pathtrack_repo.insert(
                employee_hire_history_id=employee_hire_history_id,
                registry_id=None,
                date_path_track=date_path_track,
                declarated_path_id=coord.coordinate_id,
                in_behalf_of_id=in_behalf_of_id,
                reimbursement_type="CARBURANTE",
                number_of_trips=number_of_trips,
                road_km=coord.road_km_to_workplace,
                rate_id_used=rate.rate_id,
                taxi_total_eur=None,
                computed_amount_eur=amount,
                status="DRAFT",
                submitted_on=None,
            )
            self._insert_docs(
                path_track_id=new_id,
                sheet_pdf=sheet_pdf,
                receipt_pdfs=receipt_pdfs,
                sheet_title=f"Foglio di Percorso {date_path_track:%Y-%m}",
                receipt_title_prefix=f"Ricevuta distributore {date_path_track:%Y-%m}",
            )
            conn.commit()
            return new_id
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.autocommit = prev_autocommit

    def create_draft_taxi(
        self,
        *,
        employee_hire_history_id: int,
        date_path_track: date,
        number_of_trips: int,
        receipt_amounts: Sequence[float],
        sheet_pdf: Optional[bytes],
        receipt_pdfs: Sequence[bytes],
        in_behalf_of_id: Optional[int] = None,
    ) -> int:
        self._validate_common(
            number_of_trips=number_of_trips,
            sheet_pdf=sheet_pdf,
            receipt_pdfs=receipt_pdfs,
        )
        if not receipt_amounts or all(a == 0 for a in receipt_amounts):
            raise InvalidInputError("almeno una ricevuta con importo > 0 obbligatoria")
        if not receipt_pdfs:
            raise InvalidInputError("almeno una ricevuta taxi (PDF) obbligatoria")

        if not can_create_draft_for(date_path_track):
            raise DeadlineClosedError(
                f"Periodo di inserimento per {date_path_track:%Y-%m} non aperto"
            )

        target_employee_id = in_behalf_of_id or employee_hire_history_id

        coord = self._coord_repo.find_active(target_employee_id)
        if coord is None:
            raise NoActiveCoordinateError(
                f"Nessun punto di partenza attivo per dipendente {target_employee_id}"
            )

        existing = self._pathtrack_repo.find_active_for_month(
            employee_hire_history_id=target_employee_id,
            date_path_track=date_path_track,
        )
        if existing is not None:
            raise DuplicateDeclarationError(
                f"Esiste gia' una dichiarazione attiva per {date_path_track}"
            )

        amount = compute_taxi_reimbursement(receipt_amounts)

        conn = self._connection_factory()
        prev_autocommit = getattr(conn, "autocommit", True)
        try:
            conn.autocommit = False
            new_id = self._pathtrack_repo.insert(
                employee_hire_history_id=employee_hire_history_id,
                registry_id=None,
                date_path_track=date_path_track,
                declarated_path_id=coord.coordinate_id,
                in_behalf_of_id=in_behalf_of_id,
                reimbursement_type="TAXI",
                number_of_trips=number_of_trips,
                road_km=coord.road_km_to_workplace,
                rate_id_used=None,
                taxi_total_eur=amount,
                computed_amount_eur=amount,
                status="DRAFT",
                submitted_on=None,
            )
            self._insert_docs(
                path_track_id=new_id,
                sheet_pdf=sheet_pdf,
                receipt_pdfs=receipt_pdfs,
                sheet_title=f"Foglio di Percorso {date_path_track:%Y-%m}",
                receipt_title_prefix=f"Ricevuta taxi {date_path_track:%Y-%m}",
            )
            conn.commit()
            return new_id
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.autocommit = prev_autocommit

    # ---- update draft ----------------------------------------------------

    def update_draft_fuel(
        self,
        *,
        path_track_id: int,
        employee_hire_history_id: int,
        number_of_trips: int,
        sheet_pdf: Optional[bytes],
        receipt_pdfs: Sequence[bytes],
    ) -> None:
        self._validate_common(
            number_of_trips=number_of_trips,
            sheet_pdf=sheet_pdf,
            receipt_pdfs=receipt_pdfs,
        )
        if not receipt_pdfs:
            raise InvalidInputError("almeno una ricevuta carburante obbligatoria")

        row = self._pathtrack_repo.find_by_id(
            path_track_id=path_track_id,
            employee_hire_history_id=employee_hire_history_id,
        )
        if row is None:
            raise NotADraftError("Dichiarazione non trovata o non posseduta")
        if row.status != "DRAFT":
            raise NotADraftError("Dichiarazione non e' in stato DRAFT")
        if not can_create_draft_for(row.date_path_track):
            raise DeadlineClosedError(
                f"Periodo di modifica per {row.date_path_track:%Y-%m} chiuso"
            )

        coord = self._coord_repo.find_active(employee_hire_history_id)
        if coord is None:
            raise NoActiveCoordinateError(
                "Nessun punto di partenza attivo"
            )
        rate = self._rate_repo.find_for_date(row.date_path_track)
        if rate is None:
            raise NoRateConfiguredError(
                f"Nessun rate configurato per {row.date_path_track}"
            )

        amount = compute_fuel_reimbursement(
            road_km_one_way=coord.road_km_to_workplace,
            number_of_trips=number_of_trips,
            avg_consumption_km_l=rate.avg_consumption_km_l,
            avg_fuel_price_eur_l=rate.avg_fuel_price_eur_l,
        )

        conn = self._connection_factory()
        prev_autocommit = getattr(conn, "autocommit", True)
        try:
            conn.autocommit = False
            self._pathtrack_repo.update_draft(
                path_track_id=path_track_id,
                employee_hire_history_id=employee_hire_history_id,
                reimbursement_type="CARBURANTE",
                number_of_trips=number_of_trips,
                road_km=coord.road_km_to_workplace,
                rate_id_used=rate.rate_id,
                taxi_total_eur=None,
                computed_amount_eur=amount,
            )
            self._doc_repo.soft_delete_all_for_pathtrack(path_track_id=path_track_id)
            self._insert_docs(
                path_track_id=path_track_id,
                sheet_pdf=sheet_pdf,
                receipt_pdfs=receipt_pdfs,
                sheet_title=f"Foglio di Percorso {row.date_path_track:%Y-%m}",
                receipt_title_prefix=f"Ricevuta distributore {row.date_path_track:%Y-%m}",
            )
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.autocommit = prev_autocommit

    def update_draft_taxi(
        self,
        *,
        path_track_id: int,
        employee_hire_history_id: int,
        number_of_trips: int,
        receipt_amounts: Sequence[float],
        sheet_pdf: Optional[bytes],
        receipt_pdfs: Sequence[bytes],
    ) -> None:
        self._validate_common(
            number_of_trips=number_of_trips,
            sheet_pdf=sheet_pdf,
            receipt_pdfs=receipt_pdfs,
        )
        if not receipt_amounts or all(a == 0 for a in receipt_amounts):
            raise InvalidInputError("almeno una ricevuta con importo > 0 obbligatoria")
        if not receipt_pdfs:
            raise InvalidInputError("almeno una ricevuta taxi (PDF) obbligatoria")

        row = self._pathtrack_repo.find_by_id(
            path_track_id=path_track_id,
            employee_hire_history_id=employee_hire_history_id,
        )
        if row is None:
            raise NotADraftError("Dichiarazione non trovata o non posseduta")
        if row.status != "DRAFT":
            raise NotADraftError("Dichiarazione non e' in stato DRAFT")
        if not can_create_draft_for(row.date_path_track):
            raise DeadlineClosedError(
                f"Periodo di modifica per {row.date_path_track:%Y-%m} chiuso"
            )

        coord = self._coord_repo.find_active(employee_hire_history_id)
        if coord is None:
            raise NoActiveCoordinateError("Nessun punto di partenza attivo")

        amount = compute_taxi_reimbursement(receipt_amounts)

        conn = self._connection_factory()
        prev_autocommit = getattr(conn, "autocommit", True)
        try:
            conn.autocommit = False
            self._pathtrack_repo.update_draft(
                path_track_id=path_track_id,
                employee_hire_history_id=employee_hire_history_id,
                reimbursement_type="TAXI",
                number_of_trips=number_of_trips,
                road_km=coord.road_km_to_workplace,
                rate_id_used=None,
                taxi_total_eur=amount,
                computed_amount_eur=amount,
            )
            self._doc_repo.soft_delete_all_for_pathtrack(path_track_id=path_track_id)
            self._insert_docs(
                path_track_id=path_track_id,
                sheet_pdf=sheet_pdf,
                receipt_pdfs=receipt_pdfs,
                sheet_title=f"Foglio di Percorso {row.date_path_track:%Y-%m}",
                receipt_title_prefix=f"Ricevuta taxi {row.date_path_track:%Y-%m}",
            )
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.autocommit = prev_autocommit

    # ---- submit ----------------------------------------------------------

    def submit(
        self,
        *,
        path_track_id: int,
        employee_hire_history_id: int,
        full_name: str,
        force: bool = False,
    ) -> tuple[int, bool]:
        """Invia (conferma) una bozza. Ritorna (registry_id, bnr_rate_resolved)
        dove bnr_rate_resolved=False indica che il tasso BNR e' stato NULL.

        Args:
            force: se True, salta il check `can_submit_for` (uso admin per
                   inviare bozze scadute oltre il 5 del mese successivo).
                   Il check di stato DRAFT e ownership rimangono attivi.
        """
        row = self._pathtrack_repo.find_by_id(
            path_track_id=path_track_id,
            employee_hire_history_id=employee_hire_history_id,
        )
        if row is None:
            raise NotADraftError("Dichiarazione non trovata o non posseduta")
        if row.status != "DRAFT":
            raise NotADraftError("Dichiarazione gia' inviata o cancellata")
        if not force and not can_submit_for(row.date_path_track):
            raise DeadlineClosedError(
                f"Finestra di invio chiusa per {row.date_path_track:%Y-%m} "
                "(submit consentito solo dal 1 al 5 del mese successivo)"
            )

        # Try to fetch BNR rate (if currency service available)
        bnr_rate = None
        bnr_resolved = True
        if self._currency_service is not None:
            try:
                resolved = self._currency_service.resolve_for(
                    date.today(), user_sys=full_name,
                )
                bnr_rate = resolved.value_ron_per_eur
            except RateNotResolvableError:
                # Graceful degradation: submit proceeds with NULL rate
                bnr_rate = None
                bnr_resolved = False
        # else: no currency service configured -> rate stays NULL but it's
        # an intended scenario (e.g., legacy installs); bnr_resolved stays True.

        conn = self._connection_factory()
        prev_autocommit = getattr(conn, "autocommit", True)
        try:
            conn.autocommit = False
            registry_id = self._registry_repo.generate(issued_by_full_name=full_name)
            ok = self._pathtrack_repo.mark_as_submitted(
                path_track_id=path_track_id,
                employee_hire_history_id=employee_hire_history_id,
                registry_id=registry_id,
                bnr_rate=bnr_rate,
            )
            if not ok:
                raise NotADraftError("Submit fallito: stato cambiato durante la transazione")
            conn.commit()
            return registry_id, bnr_resolved
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.autocommit = prev_autocommit

    # ---- delete / read ---------------------------------------------------

    def delete(self, *, path_track_id, employee_hire_history_id):
        """Soft delete: only DRAFTs can be deleted (enforced at repo level)."""
        return self._pathtrack_repo.soft_delete(
            path_track_id=path_track_id,
            employee_hire_history_id=employee_hire_history_id,
        )

    def list_for_employee(self, *, employee_hire_history_id):
        return self._pathtrack_repo.list_for_employee(
            employee_hire_history_id=employee_hire_history_id,
        )

    def find_by_id(self, *, path_track_id, employee_hire_history_id):
        return self._pathtrack_repo.find_by_id(
            path_track_id=path_track_id,
            employee_hire_history_id=employee_hire_history_id,
        )
