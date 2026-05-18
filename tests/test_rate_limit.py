"""Test del rate limiter in-memory."""
from __future__ import annotations

from freezegun import freeze_time

from fdp_app.auth.rate_limit import LoginRateLimiter


def test_allows_first_attempts_below_limit():
    rl = LoginRateLimiter(max_attempts=3, window_seconds=60)
    assert rl.is_blocked("alice") is False
    rl.register_failure("alice")
    assert rl.is_blocked("alice") is False
    rl.register_failure("alice")
    assert rl.is_blocked("alice") is False


def test_blocks_after_max_attempts():
    rl = LoginRateLimiter(max_attempts=3, window_seconds=60)
    rl.register_failure("alice")
    rl.register_failure("alice")
    rl.register_failure("alice")
    assert rl.is_blocked("alice") is True


def test_separates_users():
    rl = LoginRateLimiter(max_attempts=2, window_seconds=60)
    rl.register_failure("alice")
    rl.register_failure("alice")
    assert rl.is_blocked("alice") is True
    assert rl.is_blocked("bob") is False


def test_window_expires():
    with freeze_time("2026-05-17 10:00:00") as frozen:
        rl = LoginRateLimiter(max_attempts=2, window_seconds=60)
        rl.register_failure("alice")
        rl.register_failure("alice")
        assert rl.is_blocked("alice") is True

        frozen.tick(delta=61)  # 61 secondi dopo
        assert rl.is_blocked("alice") is False


def test_register_success_clears_failures():
    rl = LoginRateLimiter(max_attempts=2, window_seconds=60)
    rl.register_failure("alice")
    rl.register_success("alice")
    rl.register_failure("alice")
    assert rl.is_blocked("alice") is False
