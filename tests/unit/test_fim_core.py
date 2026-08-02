"""Testes do Core FIM (Sprint 5 — File Integrity Monitor).

Cobre: models (BaselineEntry/Baseline/Snapshot/FimDiff/ChangeType), ids,
scanner (scan_snapshot/compare_baseline_snapshot), baseline
(create/load/save + round-trip validado) e FimStore (persistência).
"""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.core.exceptions import (
    BaselineCorruptionError,
    BaselineNotFoundError,
    FimError,
    UnsupportedAlgorithmError,
)
from app.core.fim import (
    Baseline,
    BaselineEntry,
    ChangeType,
    FimDiff,
    FimStore,
    Snapshot,
    compare_baseline_snapshot,
    create_baseline,
    load_baseline,
    save_baseline,
    scan_snapshot,
)
from app.core.fim.baseline import _round_trip_validate
from app.core.fim.ids import build_baseline_id
from app.core.fim.models import FimDiff as FimDiffModel


def _write_file(path: Path, content: str = "hello") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


@pytest.fixture
def target_dir(tmp_path: Path) -> Path:
    """Diretório de exemplo com 2 arquivos para as varreduras."""
    root = tmp_path / "target"
    _write_file(root / "a.txt", "aaa")
    _write_file(root / "sub" / "b.txt", "bbb")
    return root


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class TestModels:
    def test_baseline_entry_to_dict_roundtrip(self) -> None:
        entry = BaselineEntry(
            path="a.txt",
            hexdigest="ab" * 32,
            size_bytes=3,
            mtime_iso="2026-08-02T00:00:00+00:00",
            permissions="644",
        )
        data = entry.to_dict()
        assert data["path"] == "a.txt"
        assert data["permissions"] == "644"
        restored = BaselineEntry.from_dict(data)
        assert restored == entry

    def test_baseline_entry_roundtrip_without_permissions(self) -> None:
        entry = BaselineEntry(
            path="a.txt", hexdigest="ab" * 32, size_bytes=1, mtime_iso="2026-08-02T00:00:00+00:00"
        )
        restored = BaselineEntry.from_dict(entry.to_dict())
        assert restored == entry
        assert restored.permissions is None

    def test_baseline_to_dict_roundtrip(self) -> None:
        baseline = Baseline(
            baseline_id="fim_sha256_20260802T120000Z",
            algorithm="SHA256",
            created_at="2026-08-02T12:00:00+00:00",
            root="C:/tmp",
            entries=(
                BaselineEntry(
                    path="a.txt",
                    hexdigest="ab" * 32,
                    size_bytes=1,
                    mtime_iso="2026-08-02T12:00:00+00:00",
                ),
            ),
        )
        restored = Baseline.from_dict(baseline.to_dict())
        assert restored == baseline

    def test_snapshot_from_baseline(self) -> None:
        baseline = Baseline(
            baseline_id="fim_sha256_20260802T120000Z",
            algorithm="SHA256",
            created_at="2026-08-02T12:00:00+00:00",
            root="C:/tmp",
        )
        snapshot = Snapshot.from_baseline(baseline)
        assert snapshot.root == baseline.root
        assert snapshot.algorithm == baseline.algorithm

    def test_fim_diff_changed_property(self) -> None:
        diff = FimDiff(
            baseline_id="x",
            algorithm="SHA256",
            scanned_at="t",
            added=("a",),
            modified=("b", "c"),
            removed=("d",),
            unchanged=("e",),
        )
        assert diff.changed == 4

    def test_change_type_values(self) -> None:
        assert ChangeType.ADDED.value == "added"
        assert ChangeType.MODIFIED.value == "modified"
        assert ChangeType.REMOVED.value == "removed"
        assert ChangeType.UNCHANGED.value == "unchanged"

    def test_fim_diff_model_alias(self) -> None:
        assert FimDiffModel is FimDiff


# ---------------------------------------------------------------------------
# IDs
# ---------------------------------------------------------------------------


class TestIds:
    def test_build_baseline_id_format(self) -> None:
        now = datetime(2026, 8, 2, 12, 0, 0, tzinfo=UTC)
        assert build_baseline_id("SHA256", now) == "fim_sha256_20260802T120000Z"

    def test_build_baseline_id_default_now(self) -> None:
        assert build_baseline_id("SHA1").startswith("fim_sha1_")


# ---------------------------------------------------------------------------
# Scanner
# ---------------------------------------------------------------------------


class TestScanner:
    def test_scan_snapshot_recursive(self, target_dir: Path) -> None:
        snapshot = scan_snapshot(target_dir)
        assert snapshot.algorithm == "SHA256"
        paths = [e.path for e in snapshot.entries]
        assert paths == ["a.txt", "sub/b.txt"]  # ordenado, POSIX

    def test_scan_snapshot_not_recursive(self, target_dir: Path) -> None:
        snapshot = scan_snapshot(target_dir, recursive=False)
        assert [e.path for e in snapshot.entries] == ["a.txt"]

    def test_scan_snapshot_single_file(self, tmp_path: Path) -> None:
        f = tmp_path / "single.txt"
        f.write_text("data", encoding="utf-8")
        snapshot = scan_snapshot(f)
        assert [e.path for e in snapshot.entries] == ["single.txt"]

    def test_scan_snapshot_entry_metadata(self, target_dir: Path) -> None:
        snapshot = scan_snapshot(target_dir)
        entry = snapshot.entries[0]
        assert entry.size_bytes > 0
        assert entry.permissions is not None
        # mtime ISO parseável
        datetime.fromisoformat(entry.mtime_iso)

    def test_scan_snapshot_missing_target(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            scan_snapshot(tmp_path / "nope")

    def test_scan_snapshot_sha1(self, target_dir: Path) -> None:
        snapshot = scan_snapshot(target_dir, algorithm="SHA1")
        assert snapshot.algorithm == "SHA1"
        assert len(snapshot.entries[0].hexdigest) == 40

    def test_scan_snapshot_invalid_chunk(self, target_dir: Path) -> None:
        with pytest.raises(ValueError):
            scan_snapshot(target_dir, chunk_size=0)

    @pytest.mark.skipif(os.name != "nt", reason="teste específico de Windows")
    def test_scan_snapshot_absolute_windows(self, tmp_path: Path) -> None:
        snapshot = scan_snapshot(tmp_path)
        assert Path(snapshot.root).is_absolute()


class TestCompare:
    def _make_baseline(
        self,
        root: Path,
        paths: list[tuple[str, str]],
        baseline_id: str = "fim_sha256_20260802T120000Z",
    ) -> Baseline:
        entries = tuple(
            BaselineEntry(
                path=path,
                hexdigest=("ab" * 32) if digest == "ab" else ("cd" * 32),
                size_bytes=len(digest),
                mtime_iso="2026-08-02T00:00:00+00:00",
            )
            for path, digest in paths
        )
        return Baseline(
            baseline_id=baseline_id,
            algorithm="SHA256",
            created_at="2026-08-02T12:00:00+00:00",
            root=str(root),
            entries=entries,
        )

    def _make_snapshot(
        self,
        root: Path,
        paths: list[tuple[str, str]],
        baseline_id: str = "fim_sha256_20260802T120000Z",
    ) -> Snapshot:
        baseline = self._make_baseline(root, paths, baseline_id)
        return Snapshot.from_baseline(baseline)

    def test_compare_no_changes(self, tmp_path: Path) -> None:
        baseline = self._make_baseline(tmp_path, [("a.txt", "ab"), ("b.txt", "cd")])
        snapshot = self._make_snapshot(tmp_path, [("a.txt", "ab"), ("b.txt", "cd")])
        diff = compare_baseline_snapshot(baseline, snapshot)
        assert diff.changed == 0
        assert diff.unchanged == ("a.txt", "b.txt")

    def test_compare_added_modified_removed(self, tmp_path: Path) -> None:
        baseline = self._make_baseline(tmp_path, [("a.txt", "ab"), ("b.txt", "cd")])
        snapshot = self._make_snapshot(tmp_path, [("a.txt", "ef"), ("c.txt", "ab")])
        diff = compare_baseline_snapshot(baseline, snapshot)
        assert diff.added == ("c.txt",)
        assert diff.modified == ("a.txt",)
        assert diff.removed == ("b.txt",)
        assert diff.changed == 3

    def test_compare_algorithm_mismatch(self, tmp_path: Path) -> None:
        baseline = self._make_baseline(tmp_path, [("a.txt", "ab")])
        snapshot = Snapshot(
            root=str(tmp_path),
            algorithm="SHA1",
            created_at="t",
            entries=(
                BaselineEntry(
                    path="a.txt",
                    hexdigest="ab" * 20,
                    size_bytes=1,
                    mtime_iso="2026-08-02T00:00:00+00:00",
                ),
            ),
        )
        with pytest.raises(FimError):
            compare_baseline_snapshot(baseline, snapshot)

    def test_compare_root_mismatch(self, tmp_path: Path) -> None:
        baseline = self._make_baseline(tmp_path / "one", [("a.txt", "ab")])
        snapshot = self._make_snapshot(tmp_path / "two", [("a.txt", "ab")])
        with pytest.raises(FimError):
            compare_baseline_snapshot(baseline, snapshot)


# ---------------------------------------------------------------------------
# Baseline (create/load/save + round-trip)
# ---------------------------------------------------------------------------


class TestBaselineCreate:
    def test_create_baseline(self, target_dir: Path) -> None:
        now = datetime(2026, 8, 2, 12, 0, 0, tzinfo=UTC)
        baseline = create_baseline(target_dir, now=now)
        assert baseline.baseline_id == "fim_sha256_20260802T120000Z"
        assert baseline.version == 1
        assert len(baseline.entries) == 2
        assert [e.path for e in baseline.entries] == ["a.txt", "sub/b.txt"]

    def test_create_baseline_sha1_alg(self, target_dir: Path) -> None:
        baseline = create_baseline(target_dir, algorithm="MD5")
        assert baseline.algorithm == "MD5"

    def test_create_baseline_invalid_algorithm(self, target_dir: Path) -> None:
        with pytest.raises(UnsupportedAlgorithmError):
            create_baseline(target_dir, algorithm="NOPE")


class TestBaselineRoundTrip:
    def test_save_and_load_roundtrip(self, target_dir: Path, tmp_path: Path) -> None:
        baseline = create_baseline(target_dir)
        out = tmp_path / "b.json"
        save_baseline(baseline, out)
        loaded = load_baseline(out)
        assert loaded == baseline

    def test_save_is_deterministic(self, target_dir: Path, tmp_path: Path) -> None:
        baseline = create_baseline(target_dir)
        first = tmp_path / "one.json"
        second = tmp_path / "two.json"
        save_baseline(baseline, first)
        save_baseline(baseline, second)
        assert first.read_bytes() == second.read_bytes()

    def test_load_missing_file(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            load_baseline(tmp_path / "missing.json")


class TestBaselineCorruption:
    def _valid_dict(self, target_dir: Path) -> dict:
        baseline = create_baseline(target_dir)
        return baseline.to_dict()

    def _write(self, tmp_path: Path, data: object) -> Path:
        path = tmp_path / "b.json"
        path.write_text(json.dumps(data) if not isinstance(data, str) else data, encoding="utf-8")
        return path

    def test_malformed_json(self, tmp_path: Path) -> None:
        path = self._write(tmp_path, "{not json")
        with pytest.raises(BaselineCorruptionError):
            load_baseline(path)

    def test_not_a_dict(self, tmp_path: Path) -> None:
        path = self._write(tmp_path, [1, 2])
        with pytest.raises(BaselineCorruptionError):
            load_baseline(path)

    def test_wrong_version(self, target_dir: Path, tmp_path: Path) -> None:
        data = self._valid_dict(target_dir)
        data["version"] = 99
        with pytest.raises(BaselineCorruptionError):
            load_baseline(self._write(tmp_path, data))

    def test_invalid_baseline_id(self, target_dir: Path, tmp_path: Path) -> None:
        data = self._valid_dict(target_dir)
        data["baseline_id"] = "baseline_errada"
        with pytest.raises(BaselineCorruptionError):
            load_baseline(self._write(tmp_path, data))

    def test_absolute_path_rejected(self, target_dir: Path, tmp_path: Path) -> None:
        data = self._valid_dict(target_dir)
        entries = list(data["entries"])
        entries[0]["path"] = "C:/abs/path.txt"
        data["entries"] = entries
        with pytest.raises(BaselineCorruptionError):
            load_baseline(self._write(tmp_path, data))

    def test_dotdot_path_rejected(self, target_dir: Path, tmp_path: Path) -> None:
        data = self._valid_dict(target_dir)
        entries = list(data["entries"])
        entries[0]["path"] = "../escaped.txt"
        data["entries"] = entries
        with pytest.raises(BaselineCorruptionError):
            load_baseline(self._write(tmp_path, data))

    def test_duplicate_path_rejected(self, target_dir: Path, tmp_path: Path) -> None:
        data = self._valid_dict(target_dir)
        entries = list(data["entries"])
        entries[0]["path"] = entries[1]["path"]
        data["entries"] = entries
        with pytest.raises(BaselineCorruptionError):
            load_baseline(self._write(tmp_path, data))

    def test_bad_digest_rejected(self, target_dir: Path, tmp_path: Path) -> None:
        data = self._valid_dict(target_dir)
        entries = list(data["entries"])
        entries[0]["hexdigest"] = "zz-not-hex"
        data["entries"] = entries
        with pytest.raises(BaselineCorruptionError):
            load_baseline(self._write(tmp_path, data))

    def test_wrong_digest_length_rejected(self, target_dir: Path, tmp_path: Path) -> None:
        data = self._valid_dict(target_dir)
        entries = list(data["entries"])
        entries[0]["hexdigest"] = "ab" * 20  # SHA1 length, mas algoritmo SHA256
        data["entries"] = entries
        with pytest.raises(BaselineCorruptionError):
            load_baseline(self._write(tmp_path, data))

    def test_negative_size_rejected(self, target_dir: Path, tmp_path: Path) -> None:
        data = self._valid_dict(target_dir)
        entries = list(data["entries"])
        entries[0]["size_bytes"] = -5
        data["entries"] = entries
        with pytest.raises(BaselineCorruptionError):
            load_baseline(self._write(tmp_path, data))


# ---------------------------------------------------------------------------
# FimStore
# ---------------------------------------------------------------------------


class TestFimStore:
    def test_save_and_load(self, target_dir: Path, tmp_path: Path) -> None:
        store = FimStore(tmp_path / "fim", db_path=tmp_path / "test.db")
        baseline = create_baseline(target_dir)
        baseline_id = store.save(baseline)
        assert baseline_id == baseline.baseline_id
        loaded = store.load(baseline_id)
        assert loaded == baseline

    def test_list_order_newest_first(self, target_dir: Path, tmp_path: Path) -> None:
        store = FimStore(tmp_path / "fim", db_path=tmp_path / "test.db")
        b1 = create_baseline(target_dir, now=datetime(2026, 8, 2, 10, 0, 0, tzinfo=UTC))
        b2 = create_baseline(target_dir, now=datetime(2026, 8, 2, 11, 0, 0, tzinfo=UTC))
        store.save(b1)
        store.save(b2)
        ids = [item["id"] for item in store.list()]
        assert ids[0] == b2.baseline_id
        assert ids[1] == b1.baseline_id

    def test_list_metadata_fields(self, target_dir: Path, tmp_path: Path) -> None:
        store = FimStore(tmp_path / "fim", db_path=tmp_path / "test.db")
        baseline = create_baseline(target_dir)
        store.save(baseline)
        meta = store.list()[0]
        assert meta["algorithm"] == "SHA256"
        assert meta["entries"] == 2
        assert "root" in meta
        assert "created_at" in meta

    def test_delete(self, target_dir: Path, tmp_path: Path) -> None:
        store = FimStore(tmp_path / "fim", db_path=tmp_path / "test.db")
        baseline = create_baseline(target_dir)
        baseline_id = store.save(baseline)
        assert store.delete(baseline_id) is True
        assert store.delete(baseline_id) is False

    def test_load_missing_raises(self, tmp_path: Path) -> None:
        store = FimStore(tmp_path / "fim", db_path=tmp_path / "test.db")
        with pytest.raises(BaselineNotFoundError):
            store.load("fim_sha256_20260802T000000Z")

    def test_unsafe_id_rejected(self, tmp_path: Path) -> None:
        store = FimStore(tmp_path / "fim", db_path=tmp_path / "test.db")
        with pytest.raises(BaselineNotFoundError):
            store.load("../escape")

    def test_build_id_static(self) -> None:
        now = datetime(2026, 8, 2, 12, 0, 0, tzinfo=UTC)
        assert FimStore.build_id("SHA256", now) == "fim_sha256_20260802T120000Z"


# ---------------------------------------------------------------------------
# Round-trip interno (helper usado por save/load)
# ---------------------------------------------------------------------------


class TestRoundTripHelper:
    def test_round_trip_validate_passes(self, target_dir: Path) -> None:
        baseline = create_baseline(target_dir)
        _round_trip_validate(baseline)  # não levanta

    def test_round_trip_validate_unknown_algorithm(self, target_dir: Path) -> None:
        baseline = create_baseline(target_dir)
        baseline = Baseline(
            baseline_id=baseline.baseline_id,
            algorithm="NOPE",
            version=1,
            created_at=baseline.created_at,
            root=baseline.root,
            entries=baseline.entries,
        )
        with pytest.raises(UnsupportedAlgorithmError):
            _round_trip_validate(baseline)
