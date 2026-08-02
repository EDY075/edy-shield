"""Storage SQLite do EDY Shield (v2.1 — M1: SQLite Foundation).

Camada de persistência relacional do Core, 100% stdlib (``sqlite3`` — ADR-001
preservado). Centraliza conexão, schema e transações usados pelos adapters de
persistência (HistoryStore e FimStore).

Princípios:

* **ADR-001**: apenas ``sqlite3`` da stdlib — zero dependências runtime.
* **Thread-safety**: ``threading.RLock`` + conexão por operação; WAL mode.
* **Contrato preservado**: os stores públicos mantêm as mesmas assinaturas;
  este módulo é o backend interno.
* **Schema versionado**: tabelas ``scans``, ``baselines`` e
  ``baseline_entries`` (normalizado, FK cascade).
"""

from __future__ import annotations

import sqlite3
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

#: Caminho padrão do banco de dados único do EDY Shield.
DEFAULT_DB_PATH = Path.home() / ".edyshield" / "edy_shield.db"

#: Schema do banco (idempotente — CREATE IF NOT EXISTS).
_SCHEMA = """
CREATE TABLE IF NOT EXISTS scans (
    scan_id        TEXT PRIMARY KEY,
    plugin_name    TEXT NOT NULL,
    plugin_version TEXT NOT NULL,
    timestamp      TEXT NOT NULL,
    max_severity   TEXT NOT NULL,
    payload        TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS baselines (
    baseline_id TEXT PRIMARY KEY,
    algorithm   TEXT NOT NULL,
    version     INTEGER NOT NULL,
    created_at  TEXT NOT NULL,
    root        TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS baseline_entries (
    baseline_id TEXT NOT NULL
                REFERENCES baselines(baseline_id) ON DELETE CASCADE,
    path        TEXT NOT NULL,
    hexdigest   TEXT NOT NULL,
    size_bytes  INTEGER NOT NULL,
    mtime_iso   TEXT NOT NULL,
    permissions TEXT,
    PRIMARY KEY (baseline_id, path)
);

CREATE INDEX IF NOT EXISTS idx_scans_timestamp ON scans(timestamp);
CREATE INDEX IF NOT EXISTS idx_entries_baseline ON baseline_entries(baseline_id);
"""


class SQLiteDb:
    """Acesso thread-safe a um banco SQLite do EDY Shield.

    Mantém uma **conexão única** (``check_same_thread=False``) protegida por
    ``threading.RLock`` — evita o custo de abrir/fechar conexão a cada
    operação (medido ~19ms/op com conexão por operação vs <1ms com conexão
    única). PRAGMAs (WAL, foreign keys) aplicados apenas na inicialização.

    Args:
        db_path: Caminho do arquivo ``.db``; criado (e o schema aplicado)
            automaticamente quando não existe.
    """

    def __init__(self, db_path: Path = DEFAULT_DB_PATH) -> None:
        self._db_path = db_path
        self._lock = threading.RLock()
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self._db_path), timeout=30, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        try:
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA foreign_keys=ON")
            self.initialize()
        except BaseException:
            self._conn.close()
            raise

    @property
    def db_path(self) -> Path:
        """Caminho do arquivo de banco de dados."""
        return self._db_path

    def initialize(self) -> None:
        """Criar o schema (idempotente) se o banco ainda não existir."""
        with self._lock:
            self._conn.executescript(_SCHEMA)

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        """Expor a conexão única com lock e commit/rollback por operação.

        A conexão é única (inicializada em ``__init__``); o RLock serializa
        o acesso entre threads do servidor multithread.
        """
        with self._lock:
            try:
                yield self._conn
                self._conn.commit()
            except BaseException:
                self._conn.rollback()
                raise

    def close(self) -> None:
        """Fechar a conexão (liberar recursos)."""
        with self._lock:
            self._conn.close()

    def execute(self, sql: str, params: tuple[Any, ...] = ()) -> int:
        """Executar um INSERT/UPDATE/DELETE e retornar o número de linhas."""
        with self._connect() as conn:
            cursor = conn.execute(sql, params)
            return cursor.rowcount

    def executemany(self, sql: str, seq: list[tuple[Any, ...]]) -> int:
        """Executar um INSERT em lote e retornar o número de linhas."""
        with self._connect() as conn:
            cursor = conn.executemany(sql, seq)
            return cursor.rowcount

    def transaction(self, operations: list[tuple[str, tuple[Any, ...]]]) -> None:
        """Executar múltiplas operações em uma única transação atômica.

        Útil quando um registro é composto (ex.: baseline + entries). O
        commit ocorre apenas ao final; qualquer erro desfaz tudo.

        Args:
            operations: Lista de ``(sql, params)`` executadas em ordem.
        """
        with self._connect() as conn:
            for sql, params in operations:
                conn.execute(sql, params)

    def query(self, sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
        """Executar um SELECT e retornar lista de dicionários."""
        with self._connect() as conn:
            cursor = conn.execute(sql, params)
            return [dict(row) for row in cursor.fetchall()]

    def query_one(self, sql: str, params: tuple[Any, ...] = ()) -> dict[str, Any] | None:
        """Executar um SELECT e retornar um dicionário ou ``None``."""
        rows = self.query(sql, params)
        return rows[0] if rows else None

    def scalar(self, sql: str, params: tuple[Any, ...] = ()) -> Any | None:
        """Executar um SELECT e retornar o primeiro valor da primeira linha."""
        with self._connect() as conn:
            cursor = conn.execute(sql, params)
            row = cursor.fetchone()
            return row[0] if row else None
