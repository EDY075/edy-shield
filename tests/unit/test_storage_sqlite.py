"""Testes da M1 — SQLite Foundation (v2.1).

Cobre: SQLiteDb (schema, queries, transação atômica), migração JSON→SQLite
automática, fallback de leitura legado e ARES-QA-033 (baseline_id único).
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.core.fim import FimStore, create_baseline
from app.core.storage import DEFAULT_DB_PATH, SQLiteDb
from app.plugins import Evidence, ScanResult, Severity
from app.services.history import HistoryStore


def _make_result(
    plugin: str = "hash_checker",
    severity: str = "INFO",
    ts: datetime | None = None,
) -> ScanResult:
    return ScanResult(
        plugin_name=plugin,
        plugin_version="2.0.0",
        timestamp=ts or datetime(2026, 8, 2, 12, 0, 0, tzinfo=UTC),
        summary="ok",
        findings=(Evidence(severity=Severity(severity), message="x"),),
        stats={"total": 1},
    )


# ---------------------------------------------------------------------------
# SQLiteDb
# ---------------------------------------------------------------------------


class TestSQLiteDb:
    def test_initialize_creates_schema(self, tmp_path: Path) -> None:
        db = SQLiteDb(tmp_path / "test.db")
        tables = {
            row["name"] for row in db.query("SELECT name FROM sqlite_master WHERE type='table'")
        }
        assert {"scans", "baselines", "baseline_entries"} <= tables

    def test_execute_and_query(self, tmp_path: Path) -> None:
        db = SQLiteDb(tmp_path / "test.db")
        db.execute(
            "INSERT INTO scans (scan_id, plugin_name, plugin_version, timestamp, max_severity, payload) VALUES (?,?,?,?,?,?)",
            ("a", "p", "1", "t", "INFO", "{}"),
        )
        rows = db.query("SELECT scan_id FROM scans")
        assert rows == [{"scan_id": "a"}]

    def test_query_one_none(self, tmp_path: Path) -> None:
        db = SQLiteDb(tmp_path / "test.db")
        assert db.query_one("SELECT 1 AS x FROM scans WHERE scan_id = ?", ("nope",)) is None

    def test_scalar(self, tmp_path: Path) -> None:
        db = SQLiteDb(tmp_path / "test.db")
        db.execute(
            "INSERT INTO scans (scan_id, plugin_name, plugin_version, timestamp, max_severity, payload) VALUES (?,?,?,?,?,?)",
            ("a", "p", "1", "t", "INFO", "{}"),
        )
        assert db.scalar("SELECT COUNT(*) FROM scans") == 1

    def test_transaction_commits_all(self, tmp_path: Path) -> None:
        db = SQLiteDb(tmp_path / "test.db")
        db.transaction(
            [
                (
                    "INSERT INTO baselines (baseline_id, algorithm, version, created_at, root) VALUES (?,?,?,?,?)",
                    ("b", "SHA256", 1, "t", "/"),
                ),
                (
                    "INSERT INTO baseline_entries (baseline_id, path, hexdigest, size_bytes, mtime_iso) VALUES (?,?,?,?,?)",
                    ("b", "a.txt", "ab" * 32, 1, "m"),
                ),
            ]
        )
        assert db.scalar("SELECT COUNT(*) FROM baseline_entries") == 1

    def test_transaction_rolls_back_on_error(self, tmp_path: Path) -> None:
        import sqlite3

        db = SQLiteDb(tmp_path / "test.db")
        with pytest.raises(sqlite3.OperationalError):
            db.transaction(
                [
                    (
                        "INSERT INTO baselines (baseline_id, algorithm, version, created_at, root) VALUES (?,?,?,?,?)",
                        ("b", "SHA256", 1, "t", "/"),
                    ),
                    ("INSERT INTO nao_existe (x) VALUES (?)", ("y",)),
                ]
            )
        assert db.scalar("SELECT COUNT(*) FROM baselines") == 0

    def test_default_db_path(self) -> None:
        assert DEFAULT_DB_PATH.name == "edy_shield.db"

    def test_multithread_append(self, tmp_path: Path) -> None:
        import threading

        db = SQLiteDb(tmp_path / "test.db")
        errors: list[Exception] = []

        def worker(i: int) -> None:
            try:
                db.execute(
                    "INSERT INTO scans (scan_id, plugin_name, plugin_version, timestamp, max_severity, payload) VALUES (?,?,?,?,?,?)",
                    (f"scan_{i}", "p", "1", f"t{i}", "INFO", "{}"),
                )
            except Exception as exc:  # pragma: no cover - falha de concorrência
                errors.append(exc)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors
        assert db.scalar("SELECT COUNT(*) FROM scans") == 8


# ---------------------------------------------------------------------------
# HistoryStore — SQLite + migração + fallback
# ---------------------------------------------------------------------------


class TestHistorySqlite:
    def test_save_and_get(self, tmp_path: Path) -> None:
        store = HistoryStore(tmp_path / "history", db_path=tmp_path / "test.db")
        scan_id = store.save(_make_result())
        loaded = store.get(scan_id)
        assert loaded is not None
        assert loaded.plugin_name == "hash_checker"
        assert loaded.stats == {"total": 1}

    def test_list_order_newest_first(self, tmp_path: Path) -> None:
        store = HistoryStore(tmp_path / "history", db_path=tmp_path / "test.db")
        store.save(_make_result())
        older = _make_result(ts=datetime(2026, 8, 1, 12, 0, 0, tzinfo=UTC))
        store.save(older)
        ids = [e["id"] for e in store.list()]
        assert len(ids) == 2
        assert "20260802" in ids[0]

    def test_clear(self, tmp_path: Path) -> None:
        store = HistoryStore(tmp_path / "history", db_path=tmp_path / "test.db")
        store.save(_make_result())
        assert store.clear() == 1
        assert store.list() == []

    def test_get_missing(self, tmp_path: Path) -> None:
        store = HistoryStore(tmp_path / "history", db_path=tmp_path / "test.db")
        assert store.get("nao-existe") is None

    def test_unsafe_id_rejected(self, tmp_path: Path) -> None:
        from app.services.history import HistoryError

        store = HistoryStore(tmp_path / "history", db_path=tmp_path / "test.db")
        with pytest.raises(HistoryError):
            store.get("../escape")

    def test_get_corrupted_payload_raises(self, tmp_path: Path) -> None:
        from app.services.history import HistoryError

        db = SQLiteDb(tmp_path / "test.db")
        db.execute(
            "INSERT INTO scans (scan_id, plugin_name, plugin_version, timestamp, max_severity, payload) VALUES (?,?,?,?,?,?)",
            ("corrompido", "p", "1", "t", "INFO", "{invalid json"),
        )
        store = HistoryStore(tmp_path / "history", db_path=tmp_path / "test.db")
        with pytest.raises(HistoryError):
            store.get("corrompido")


class TestHistoryMigration:
    def test_migrates_json_and_archives(self, tmp_path: Path) -> None:
        # Cria JSON legado antes de instanciar o store
        legacy = tmp_path / "history"
        legacy.mkdir(parents=True)
        (legacy / "20260802T120000Z_hash_checker.json").write_text(
            json.dumps(_make_result().as_dict(), ensure_ascii=False), encoding="utf-8"
        )

        store = HistoryStore(legacy, db_path=tmp_path / "test.db")
        assert store.list()  # migrado
        # JSON original arquivado
        backup = tmp_path / "backup" / "history"
        assert (backup / "20260802T120000Z_hash_checker.json").exists()
        # Leitura funciona via SQLite
        assert store.get("20260802T120000Z_hash_checker") is not None

    def test_migration_idempotent(self, tmp_path: Path) -> None:
        legacy = tmp_path / "history"
        legacy.mkdir(parents=True)
        (legacy / "scan1.json").write_text(
            json.dumps(_make_result().as_dict(), ensure_ascii=False), encoding="utf-8"
        )
        HistoryStore(legacy, db_path=tmp_path / "test.db")  # migra (tabela vazia)
        store2 = HistoryStore(legacy, db_path=tmp_path / "test.db")  # idempotente
        assert len(store2.list()) == 1

    def test_migration_ignores_invalid_and_non_dict_json(self, tmp_path: Path) -> None:
        legacy = tmp_path / "history"
        legacy.mkdir(parents=True)
        (legacy / "invalido.json").write_text("{not json", encoding="utf-8")
        (legacy / "nao_dict.json").write_text("[1,2]", encoding="utf-8")
        (legacy / "valido.json").write_text(
            json.dumps(_make_result().as_dict(), ensure_ascii=False), encoding="utf-8"
        )
        store = HistoryStore(legacy, db_path=tmp_path / "test.db")
        assert len(store.list()) == 1  # só o válido migrou
        assert store.get("valido") is not None

    def test_fallback_reads_legacy_json(self, tmp_path: Path) -> None:
        # JSON não migrado (ex.: backup manual) é lido como fallback
        legacy = tmp_path / "history"
        legacy.mkdir(parents=True)
        # Instancia o store (tabela vazia, sem JSON no base_dir)
        store = HistoryStore(legacy, db_path=tmp_path / "test.db")
        # Simula registro legado criado depois
        path = legacy / "scan_legacy.json"
        path.write_text(json.dumps(_make_result().as_dict(), ensure_ascii=False), encoding="utf-8")
        # get consulta SQLite, não encontra, cai no fallback JSON
        assert store.get("scan_legacy") is not None


# ---------------------------------------------------------------------------
# FimStore — SQLite + migração + ARES-QA-033
# ---------------------------------------------------------------------------


class TestFimSqlite:
    def test_save_load_list_delete(self, tmp_path: Path) -> None:
        target = tmp_path / "target"
        target.mkdir()
        (target / "a.txt").write_text("aaa", encoding="utf-8")
        store = FimStore(tmp_path / "fim", db_path=tmp_path / "test.db")
        baseline = create_baseline(target)
        baseline_id = store.save(baseline)
        loaded = store.load(baseline_id)
        assert loaded == baseline
        meta = store.list()[0]
        assert meta["entries"] == 1
        assert store.delete(baseline_id) is True
        assert store.delete(baseline_id) is False

    def test_load_missing(self, tmp_path: Path) -> None:
        from app.core.exceptions import BaselineNotFoundError

        store = FimStore(tmp_path / "fim", db_path=tmp_path / "test.db")
        with pytest.raises(BaselineNotFoundError):
            store.load("fim_sha256_20260802T000000Z")

    def test_unsafe_id_rejected(self, tmp_path: Path) -> None:
        from app.core.exceptions import BaselineNotFoundError

        store = FimStore(tmp_path / "fim", db_path=tmp_path / "test.db")
        with pytest.raises(BaselineNotFoundError):
            store.load("../escape")


class TestFimAresQa033:
    def test_same_second_collision_gets_unique_id(self, tmp_path: Path) -> None:
        """Duas baselines no mesmo segundo NÃO colidem (ARES-QA-033)."""
        target = tmp_path / "target"
        target.mkdir()
        (target / "a.txt").write_text("aaa", encoding="utf-8")
        store = FimStore(tmp_path / "fim", db_path=tmp_path / "test.db")

        now = datetime(2026, 8, 2, 12, 0, 0, tzinfo=UTC)
        b1 = create_baseline(target, now=now)
        b2 = create_baseline(target, now=now)  # mesmo segundo → mesmo id base

        assert b1.baseline_id == b2.baseline_id
        id1 = store.save(b1)
        id2 = store.save(b2)  # segunda NÃO sobrescreve a primeira

        assert id1 != id2
        # A segunda baseline foi persistida com id único (fração de microssegundo)
        assert store.load(id1).baseline_id == id1
        assert store.load(id2).baseline_id == id2
        assert store.load(id1).entries == b1.entries
        assert store.load(id2).entries == b2.entries
        assert len(store.list()) == 2


class TestFimMigration:
    def test_migrates_json_and_archives(self, tmp_path: Path) -> None:
        target = tmp_path / "target"
        target.mkdir()
        (target / "a.txt").write_text("aaa", encoding="utf-8")

        # Gera uma baseline legada em JSON via save_baseline
        from app.core.fim import save_baseline

        baseline = create_baseline(target, now=datetime(2026, 8, 2, 12, 0, 0, tzinfo=UTC))
        legacy_dir = tmp_path / "fim"
        legacy_dir.mkdir(parents=True)
        save_baseline(baseline, legacy_dir / f"{baseline.baseline_id}.json")

        store = FimStore(legacy_dir, db_path=tmp_path / "test.db")
        assert len(store.list()) == 1
        backup = tmp_path / "backup" / "fim"
        assert (backup / f"{baseline.baseline_id}.json").exists()
        assert store.load(baseline.baseline_id) == baseline

    def test_fallback_reads_legacy_json(self, tmp_path: Path) -> None:
        target = tmp_path / "target"
        target.mkdir()
        (target / "a.txt").write_text("aaa", encoding="utf-8")
        from app.core.fim import save_baseline

        legacy_dir = tmp_path / "fim"
        legacy_dir.mkdir(parents=True)

        # Primeira baseline é migrada na init (tabela vazia → migra tudo)
        b1 = create_baseline(target, now=datetime(2026, 8, 2, 12, 0, 0, tzinfo=UTC))
        save_baseline(b1, legacy_dir / f"{b1.baseline_id}.json")
        store = FimStore(legacy_dir, db_path=tmp_path / "test.db")
        assert len(store.list()) == 1

        # Segunda baseline criada DEPOIS (tabela já tem dados → migração
        # idempotente NÃO roda) — fica como JSON legado no base_dir
        b2 = create_baseline(target, now=datetime(2026, 8, 2, 12, 1, 0, tzinfo=UTC))
        save_baseline(b2, legacy_dir / f"{b2.baseline_id}.json")

        # load de b2: não está no SQLite → fallback lê o JSON legado
        assert store.load(b2.baseline_id) == b2
