"""Rate limiter in-memory per i tentativi di login."""
from __future__ import annotations

import time
from collections import defaultdict, deque
from threading import Lock
from typing import Deque, Dict


class LoginRateLimiter:
    """Limita i tentativi di login falliti per `username` in una finestra mobile.

    Thread-safe. NON e' condiviso fra processi: in deploy multi-worker,
    ogni worker ha la propria copia (limite morbido, accettabile per V1).
    """

    def __init__(self, max_attempts: int, window_seconds: int) -> None:
        self._max = max_attempts
        self._window = window_seconds
        self._failures: Dict[str, Deque[float]] = defaultdict(deque)
        self._lock = Lock()

    def _prune(self, key: str, now: float) -> None:
        q = self._failures[key]
        while q and (now - q[0]) > self._window:
            q.popleft()

    def is_blocked(self, key: str) -> bool:
        with self._lock:
            self._prune(key, time.time())
            return len(self._failures[key]) >= self._max

    def register_failure(self, key: str) -> None:
        with self._lock:
            now = time.time()
            self._prune(key, now)
            self._failures[key].append(now)

    def register_success(self, key: str) -> None:
        with self._lock:
            self._failures[key].clear()
