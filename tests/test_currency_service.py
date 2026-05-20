"""Test del CurrencyService (cascade lookup standard->live->cached)."""
from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock

import pytest

from fdp_app.pathtracks.bnr_client import BnrRateUnavailable
from fdp_app.pathtracks.currency import (
    CurrencyService,
    ResolvedRate,
    RateNotResolvableError,
)
from fdp_app.repos.bnr_rate_repo import BnrRate


def _service():
    repo = MagicMock()
    client = MagicMock()
    repo.find_standard_for.return_value = None
    repo.find_latest_cached_for.return_value = None
    svc = CurrencyService(bnr_repo=repo, bnr_client=client)
    return svc, repo, client


def test_returns_standard_when_available():
    svc, repo, client = _service()
    repo.find_standard_for.return_value = BnrRate(
        rate_id=1, rate_value_ron_per_eur=4.9, source="STANDARD",
        valid_from=date(2026, 1, 1), valid_to=None,
    )

    result = svc.resolve_for(date(2026, 5, 20), user_sys="x")

    assert isinstance(result, ResolvedRate)
    assert result.value_ron_per_eur == pytest.approx(4.9)
    assert result.source == "STANDARD"
    assert result.stale is False
    client.fetch_eur_to_ron.assert_not_called()


def test_calls_client_when_no_standard():
    svc, repo, client = _service()
    repo.find_standard_for.return_value = None
    client.fetch_eur_to_ron.return_value = (4.97, "BNR")

    result = svc.resolve_for(date(2026, 5, 20), user_sys="test")

    assert result.value_ron_per_eur == pytest.approx(4.97)
    assert result.source == "BNR"
    assert result.stale is False
    # Persist
    repo.insert.assert_called_once()
    kwargs = repo.insert.call_args.kwargs
    assert kwargs["rate_value_ron_per_eur"] == pytest.approx(4.97)
    assert kwargs["source"] == "BNR"
    assert kwargs["valid_from"] == date(2026, 5, 20)
    assert kwargs["is_standard"] is False


def test_returns_cached_when_live_fails():
    svc, repo, client = _service()
    repo.find_standard_for.return_value = None
    client.fetch_eur_to_ron.side_effect = BnrRateUnavailable("down")
    repo.find_latest_cached_for.return_value = BnrRate(
        rate_id=5, rate_value_ron_per_eur=4.95, source="BNR",
        valid_from=date(2026, 5, 19), valid_to=None,
    )

    result = svc.resolve_for(date(2026, 5, 20), user_sys="x")

    assert result.value_ron_per_eur == pytest.approx(4.95)
    assert result.source == "BNR"
    assert result.stale is True  # cached -> stale=True


def test_raises_when_everything_fails():
    svc, repo, client = _service()
    repo.find_standard_for.return_value = None
    client.fetch_eur_to_ron.side_effect = BnrRateUnavailable("down")
    repo.find_latest_cached_for.return_value = None

    with pytest.raises(RateNotResolvableError):
        svc.resolve_for(date(2026, 5, 20), user_sys="x")


def test_cursbnr_source_persisted_correctly():
    svc, repo, client = _service()
    repo.find_standard_for.return_value = None
    client.fetch_eur_to_ron.return_value = (4.96, "CURSBNR")

    result = svc.resolve_for(date(2026, 5, 20), user_sys="x")

    assert result.source == "CURSBNR"
    kwargs = repo.insert.call_args.kwargs
    assert kwargs["source"] == "CURSBNR"
