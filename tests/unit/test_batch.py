"""Testes unitários para o módulo batch.py — hash_files e hash_directory."""

from hashlib import sha256
from pathlib import Path

import pytest

from app.core.algorithms.batch import hash_directory, hash_files
from app.core.crypto.hashing import HashAlgorithm
from app.core.exceptions import UnsupportedAlgorithmError


class TestHashDirectory:
    """hash_directory — varredura de diretórios."""

    def test_empty_directory(self, tmp_path: Path) -> None:
        results = hash_directory(tmp_path, HashAlgorithm.SHA256)
        assert results == []

    def test_single_file(self, tmp_path: Path) -> None:
        f = tmp_path / "hello.txt"
        f.write_text("hello")
        expected = sha256(b"hello").hexdigest()

        results = hash_directory(tmp_path, HashAlgorithm.SHA256)
        assert len(results) == 1
        entry, err = results[0]
        assert err is None
        assert entry is not None
        assert entry.hexdigest == expected

    def test_multiple_files_ordered(self, tmp_path: Path) -> None:
        (tmp_path / "b.txt").write_text("b")
        (tmp_path / "a.txt").write_text("a")
        (tmp_path / "c.txt").write_text("c")

        results = hash_directory(tmp_path, HashAlgorithm.SHA256)
        assert len(results) == 3
        paths = [entry.path.name for entry, _ in results if entry is not None]
        assert paths == ["a.txt", "b.txt", "c.txt"]

    def test_subdirectories_without_recursive(self, tmp_path: Path) -> None:
        (tmp_path / "top.txt").write_text("top")
        subdir = tmp_path / "sub"
        subdir.mkdir()
        (subdir / "deep.txt").write_text("deep")

        results = hash_directory(tmp_path, HashAlgorithm.SHA256, recursive=False)
        assert len(results) == 1
        entry, _ = results[0]
        assert entry is not None
        assert entry.path.name == "top.txt"

    def test_subdirectories_with_recursive(self, tmp_path: Path) -> None:
        sub = tmp_path / "sub"
        sub.mkdir()
        (sub / "deep.txt").write_text("deep")
        (tmp_path / "top.txt").write_text("top")

        results = hash_directory(tmp_path, HashAlgorithm.SHA256, recursive=True)
        assert len(results) == 2

    def test_ordering_deterministic(self, tmp_path: Path) -> None:
        for name in ["z.txt", "m.txt", "a.txt"]:
            (tmp_path / name).write_text(name)

        r1 = hash_directory(tmp_path, HashAlgorithm.SHA256)
        r2 = hash_directory(tmp_path, HashAlgorithm.SHA256)
        paths1 = [entry.path for entry, _ in r1 if entry is not None]
        paths2 = [entry.path for entry, _ in r2 if entry is not None]
        assert paths1 == paths2
        assert [p.name for p in paths1] == ["a.txt", "m.txt", "z.txt"]

    def test_invalid_algorithm_raises(self, tmp_path: Path) -> None:
        (tmp_path / "data.txt").write_text("data")
        with pytest.raises(UnsupportedAlgorithmError):
            hash_directory(tmp_path, "BLAKE2B")


class TestHashFilesList:
    def test_single_file(self, tmp_path: Path) -> None:
        f = tmp_path / "x"
        f.write_text("data")
        expected = sha256(b"data").hexdigest()
        results = hash_files([f], HashAlgorithm.SHA256)
        entry, _ = results[0]
        assert entry is not None
        assert entry.hexdigest == expected

    def test_multiple_files(self, tmp_path: Path) -> None:
        (tmp_path / "b").write_text("b")
        (tmp_path / "a").write_text("a")
        results = hash_files([tmp_path / "b", tmp_path / "a"], HashAlgorithm.SHA256)
        assert len(results) == 2
        assert results[0][0] is not None
        assert results[1][0] is not None

    def test_invalid_algorithm_in_list(self, tmp_path: Path) -> None:
        (tmp_path / "f").write_text("x")
        with pytest.raises(UnsupportedAlgorithmError):
            hash_files([tmp_path / "f"], "SHA512")

    def test_missing_file_in_batch(self, tmp_path: Path) -> None:
        missing = tmp_path / "gone"
        results = hash_files([missing], HashAlgorithm.SHA256)
        assert len(results) == 1
        entry, err = results[0]
        assert entry is None
        assert err is not None
