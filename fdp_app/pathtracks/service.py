"""Orchestrazione transazionale per la dichiarazione mensile.

Coordina:
- CoordinateRepo, RateRepo, ReimbursementCalculator,
- RegistryRepo (SP call), PathTrackRepo (INSERT),
- PathTrackDocRepo (BLOB insert per ogni PDF)

Tutto dentro una transazione pyodbc esplicita (autocommit OFF temporaneo).
"""
from __future__ import annotations

from datetime import date
from typing import Callable, Optional, Sequence

from fdp_app.pathtracks.calculator import (
    compute_fuel_reimbursement,
    compute_taxi_reimbursement,
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
    """Esiste gia' una dichiarazione attiva per lo stesso mese."""


class DeadlineClosedError(Exception):
    """Periodo di inserimento chiuso."""


class InvalidInputError(Exception):
    """Input validato lato service rifiutato."""


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
    ) -> None:
        self._coord_repo = coordinate_repo
        self._rate_repo = rate_repo
        self._registry_repo = registry_repo
        self._pathtrack_repo = pathtrack_repo
        self._doc_repo = doc_repo
        self._connection_factory = connection_factory

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

    def create_fuel(
        self,
        *,
        employee_hire_history_id: int,
        full_name: str,
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
            registry_id = self._registry_repo.generate(issued_by_full_name=full_name)
            new_id = self._pathtrack_repo.insert(
                employee_hire_history_id=employee_hire_history_id,
                registry_id=registry_id,
                date_path_track=date_path_track,
                declarated_path_id=coord.coordinate_id,
                in_behalf_of_id=in_behalf_of_id,
                reimbursement_type="CARBURANTE",
                number_of_trips=number_of_trips,
                road_km=coord.road_km_to_workplace,
                rate_id_used=rate.rate_id,
                taxi_total_eur=None,
                computed_amount_eur=amount,
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

    def create_taxi(
        self,
        *,
        employee_hire_history_id: int,
        full_name: str,
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
            registry_id = self._registry_repo.generate(issued_by_full_name=full_name)
            new_id = self._pathtrack_repo.insert(
                employee_hire_history_id=employee_hire_history_id,
                registry_id=registry_id,
                date_path_track=date_path_track,
                declarated_path_id=coord.coordinate_id,
                in_behalf_of_id=in_behalf_of_id,
                reimbursement_type="TAXI",
                number_of_trips=number_of_trips,
                road_km=coord.road_km_to_workplace,
                rate_id_used=None,
                taxi_total_eur=amount,
                computed_amount_eur=amount,
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

    def delete(self, *, path_track_id, employee_hire_history_id):
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
