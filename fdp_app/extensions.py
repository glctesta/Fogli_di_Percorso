"""Istanze condivise di estensioni Flask."""
from __future__ import annotations

from flask_wtf import CSRFProtect

csrf = CSRFProtect()
