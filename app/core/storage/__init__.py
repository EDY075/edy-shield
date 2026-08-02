"""Storage SQLite do EDY Shield (v2.1 — M1: SQLite Foundation).

Backend relacional do Core (100% stdlib — ``sqlite3``), usado pelos adapters
de persistência:

* :class:`~app.services.history.HistoryStore` — histórico de varreduras.
* :class:`~app.core.fim.store.FimStore` — baselines do File Integrity Monitor.

O banco único padrão é ``~/.edyshield/edy_shield.db``.
"""

from app.core.storage.sqlite_db import DEFAULT_DB_PATH, SQLiteDb

__all__ = ["DEFAULT_DB_PATH", "SQLiteDb"]
