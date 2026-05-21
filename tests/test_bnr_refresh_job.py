"""Test del BnrRefreshJob (pre-popola il tasso BNR del giorno)."""
from __future__ import annotations

from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from flask import Flask

from fdp_app.notifications.service import BnrRefreshJob
from fdp_app.pathtracks.currency import ResolvedRate


def _make_flask_app(tmp_path: Path, *, bnr_client=None) -> Flask:
    root = tmp_path / "fdp_app"
    root.mkdir(parents=True, exist_ok=True)
    app = Flask(__name__, root_path=str(root))
    app.config["_db"] = MagicMock()
    app.config["_bnr_client"] = bnr_client

    class FakeSettings:
        APP_URL = "http://test.local"

    app.config["_settings_cls"] = FakeSettings
    return app


def test_run_returns_value_and_source_from_currency_service(tmp_path):
    injected_client = MagicMock(name="bnr_client")
    app = _make_flask_app(tmp_path, bnr_client=injected_client)

    fake_resolved = ResolvedRate(
        value_ron_per_eur=4.97, source="BNR", stale=False,
    )

    with patch("fdp_app.pathtracks.currency.CurrencyService") as cs_cls:
        instance = cs_cls.return_value
        instance.resolve_for.return_value = fake_resolved

        value, source = BnrRefreshJob(app).run()

    assert value == pytest.approx(4.97)
    assert source == "BNR"
    instance.resolve_for.assert_called_once()
    call_args = instance.resolve_for.call_args
    assert call_args.args[0] == date.today()
    assert call_args.kwargs.get("user_sys") == "bnr-refresh-job"


def test_run_uses_injected_bnr_client_when_present(tmp_path):
    injected_client = MagicMock(name="injected_bnr_client")
    app = _make_flask_app(tmp_path, bnr_client=injected_client)

    fake_resolved = ResolvedRate(
        value_ron_per_eur=4.95, source="CURSBNR", stale=False,
    )

    with patch("fdp_app.pathtracks.currency.CurrencyService") as cs_cls, \
         patch("fdp_app.pathtracks.bnr_client.BnrRateClient") as client_cls:
        cs_cls.return_value.resolve_for.return_value = fake_resolved

        BnrRefreshJob(app).run()

    # The CurrencyService must be constructed with the *injected* client.
    cs_cls.assert_called_once()
    kwargs = cs_cls.call_args.kwargs
    assert kwargs["bnr_client"] is injected_client
    # The default BnrRateClient constructor should NOT have been called.
    client_cls.assert_not_called()


def test_run_falls_back_to_fresh_client_when_no_injection(tmp_path):
    # No _bnr_client in app.config -> get() returns None -> fallback path.
    app = _make_flask_app(tmp_path, bnr_client=None)

    fake_resolved = ResolvedRate(
        value_ron_per_eur=4.90, source="BNR", stale=False,
    )
    fresh_client = MagicMock(name="fresh_bnr_client")

    with patch("fdp_app.pathtracks.currency.CurrencyService") as cs_cls, \
         patch("fdp_app.pathtracks.bnr_client.BnrRateClient",
               return_value=fresh_client) as client_cls:
        cs_cls.return_value.resolve_for.return_value = fake_resolved

        BnrRefreshJob(app).run()

    client_cls.assert_called_once_with()
    kwargs = cs_cls.call_args.kwargs
    assert kwargs["bnr_client"] is fresh_client
