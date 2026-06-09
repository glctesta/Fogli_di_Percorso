"""Logica applicativa per il reset password via email.

Flusso:
  1. request_reset(nome_user): genera token, salva l'HASH, ritorna il token
     in chiaro + l'email di destinazione (o None se l'utente non esiste).
     Il chiamante (route) si occupa dell'invio email e NON deve rivelare
     all'utente finale se l'username esisteva o meno.
  2. validate_token(token): ritorna il NomeUser se il token e' valido.
  3. consume_token_and_set_password(token, new_password): in una sola
     transazione invalida il token e aggiorna la password.

Nota di sicurezza (password storage):
  La tabella `resetservices.dbo.tbuserkey` e' condivisa con altri sistemi
  aziendali e memorizza la password nel formato attuale (in chiaro). Questo
  service scrive nel medesimo formato per non rompere gli altri consumer.
  La migrazione a un hash (bcrypt/argon2) va decisa a livello organizzativo
  e coordinata con tutti i sistemi che leggono questa tabella; quando sara'
  fatto, l'unico punto da cambiare qui e' `_encode_password`.
"""
from __future__ import annotations

import hashlib
import re
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

from fdp_app.repos.employee_repo import EmployeeRepo, UserEmail
from fdp_app.repos.password_reset_repo import PasswordResetTokenRepo

# Durata di validita' del link di reset.
TOKEN_TTL = timedelta(minutes=30)

# Requisiti minimi della nuova password.
PASSWORD_MIN_LEN = 8


@dataclass(frozen=True)
class ResetRequest:
    """Esito di una richiesta di reset (per la route, non per l'utente)."""
    token_plain: str
    email: UserEmail


class PasswordResetService:
    def __init__(self, employee_repo: EmployeeRepo,
                 token_repo: PasswordResetTokenRepo) -> None:
        self._employees = employee_repo
        self._tokens = token_repo

    # ------------------------------------------------------------------ #
    # Hashing del token (per il DB) e codifica password (per tbuserkey)
    # ------------------------------------------------------------------ #
    @staticmethod
    def _hash_token(token_plain: str) -> str:
        return hashlib.sha256(token_plain.encode("utf-8")).hexdigest()

    @staticmethod
    def _encode_password(plain: str) -> str:
        """Codifica la password nel formato atteso da tbuserkey.

        Attualmente: in chiaro (vedi nota di sicurezza nel modulo).
        Unico punto da modificare per introdurre l'hashing.
        """
        return plain

    # ------------------------------------------------------------------ #
    # Validazione password
    # ------------------------------------------------------------------ #
    @staticmethod
    def validate_new_password(pw1: str, pw2: str) -> Optional[str]:
        """Ritorna un messaggio d'errore (chiave da tradurre) o None se ok."""
        if not pw1 or not pw2:
            return "La password e' obbligatoria."
        if pw1 != pw2:
            return "Le due password non coincidono."
        if len(pw1) < PASSWORD_MIN_LEN:
            return "La password deve avere almeno 8 caratteri."
        if not re.search(r"[A-Za-z]", pw1) or not re.search(r"\d", pw1):
            return "La password deve contenere almeno una lettera e un numero."
        return None

    # ------------------------------------------------------------------ #
    # 1) Richiesta di reset
    # ------------------------------------------------------------------ #
    def request_reset(self, nome_user: str,
                      request_ip: Optional[str] = None,
                      now: Optional[datetime] = None) -> Optional[ResetRequest]:
        """Crea un token di reset per `nome_user`.

        Ritorna ResetRequest (token in chiaro + email) se l'utente esiste e
        ha una WorkEmail; altrimenti None. La route deve comportarsi in modo
        identico in entrambi i casi verso l'utente (no user enumeration).
        """
        nome_user = (nome_user or "").strip()
        if not nome_user:
            return None

        email = self._employees.find_email_by_nomeuser(nome_user)
        if email is None:
            return None

        now = now or datetime.now()

        # Invalida eventuali token aperti precedenti: un solo link valido.
        self._tokens.invalidate_open_for_user(nome_user)

        token_plain = secrets.token_urlsafe(32)
        token_hash = self._hash_token(token_plain)
        self._tokens.insert(
            nome_user=nome_user,
            token_hash=token_hash,
            expires_at=now + TOKEN_TTL,
            request_ip=request_ip,
        )
        return ResetRequest(token_plain=token_plain, email=email)

    # ------------------------------------------------------------------ #
    # 2) Validazione del token (GET form)
    # ------------------------------------------------------------------ #
    def validate_token(self, token_plain: str,
                       now: Optional[datetime] = None) -> Optional[str]:
        """Ritorna il NomeUser se il token e' valido e consumabile, else None."""
        if not token_plain:
            return None
        now = now or datetime.now()
        rec = self._tokens.find_by_hash(self._hash_token(token_plain))
        if rec is None or not rec.is_consumable(now):
            return None
        return rec.nome_user

    # ------------------------------------------------------------------ #
    # 3) Consumo del token + aggiornamento password (POST)
    # ------------------------------------------------------------------ #
    def consume_token_and_set_password(
        self, token_plain: str, new_password: str,
        now: Optional[datetime] = None,
    ) -> bool:
        """Marca il token come usato e aggiorna la password, atomicamente.

        Ritorna True se il reset e' andato a buon fine. False se il token
        non e' (piu') valido. La transazione e' gestita dal chiamante (route)
        che dispone della connection pyodbc; qui usiamo i repo, che
        condividono la stessa connection per-request.
        """
        now = now or datetime.now()
        rec = self._tokens.find_by_hash(self._hash_token(token_plain))
        if rec is None or not rec.is_consumable(now):
            return False

        # mark_used e' condizionato a UsedAt IS NULL: se rowcount==0, un'altra
        # richiesta concorrente l'ha gia' consumato -> abort.
        if self._tokens.mark_used(rec.token_id) == 0:
            return False

        updated = self._employees.update_password(
            rec.nome_user, self._encode_password(new_password)
        )
        return updated > 0
