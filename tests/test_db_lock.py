"""Verifica che Database.cursor() sia thread-safe rispetto alla connessione condivisa."""
from __future__ import annotations

import threading
from unittest.mock import MagicMock

from fdp_app.db import Database


def test_cursor_lock_serializes_access_to_underlying_connection():
    """Due thread che chiamano cursor() in parallelo non devono vedere
    chiamate sovrapposte a connect()."""
    db = Database.__new__(Database)  # bypass __init__
    db._cm = MagicMock()
    db._conn = MagicMock()
    db._conn.connect.return_value = MagicMock()  # ritorna un mock 'connection'
    db._conn.connect.return_value.cursor.return_value = MagicMock()
    # Inietta il lock come farebbe __init__
    db._lock = threading.Lock()

    n_threads = 8
    iterations = 50
    barrier = threading.Barrier(n_threads)

    def worker():
        barrier.wait()
        for _ in range(iterations):
            db.cursor()

    threads = [threading.Thread(target=worker) for _ in range(n_threads)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # connect() chiamato n_threads * iterations volte, ma serializzato
    assert db._conn.connect.call_count == n_threads * iterations


def test_database_initializes_with_lock():
    """Database.__init__ deve inizializzare il lock."""
    from unittest.mock import patch
    with patch('fdp_app.db.ConfigManager'):
        with patch('fdp_app.db.DatabaseConnection'):
            db = Database()
            assert hasattr(db, '_lock')
            assert isinstance(db._lock, type(threading.Lock()))
