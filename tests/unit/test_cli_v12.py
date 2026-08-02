"""Testes de integração da CLI — batch hashing e checksum files (v1.2)."""

import hashlib
from pathlib import Path

import pytest

from app.cli.hash_cmd import EXIT_ERROR, EXIT_MISMATCH, EXIT_SUCCESS, main


@pytest.fixture()
def batch_dir(tmp_path: Path) -> Path:
    """Diretório com 2 arquivos e um subdiretório."""
    (tmp_path / "a.txt").write_text("aaa")
    (tmp_path / "b.txt").write_text("bbb")
    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "c.txt").write_text("ccc")
    return tmp_path


class TestHashBatchCommand:
    def test_batch_non_recursive(self, batch_dir: Path, capsys: pytest.CaptureFixture[str]) -> None:
        exit_code = main(["hash", "--batch", str(batch_dir)])
        out = capsys.readouterr().out
        assert exit_code == EXIT_SUCCESS
        # apenas arquivos do nível superior (sem sub/)
        assert "a.txt" in out
        assert "b.txt" in out
        assert "sub/c.txt" not in out

    def test_batch_recursive(self, batch_dir: Path, capsys: pytest.CaptureFixture[str]) -> None:
        exit_code = main(["hash", "--batch", "--recursive", str(batch_dir)])
        out = capsys.readouterr().out
        assert exit_code == EXIT_SUCCESS
        assert "a.txt" in out
        assert "b.txt" in out
        # sub/c.txt com qualquer separador de path (Windows vs POSIX)
        assert "c.txt" in out and "sub" in out

    def test_batch_digests_correct(
        self, batch_dir: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        main(["hash", "--batch", str(batch_dir)])
        out = capsys.readouterr().out
        a_digest = hashlib.sha256(b"aaa").hexdigest()
        assert a_digest in out

    def test_batch_stdout_has_only_digests(
        self, batch_dir: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        main(["hash", "--batch", str(batch_dir)])
        out = capsys.readouterr().out
        # cada linha: digest + 2 espaços + path
        lines = out.strip().splitlines()
        assert len(lines) == 2
        for line in lines:
            digest, sep, _name = line.partition("  ")
            assert sep == "  "
            assert len(digest) == 64


class TestChecksumCreateCommand:
    def test_create_ok(self, batch_dir: Path, capsys: pytest.CaptureFixture[str]) -> None:
        exit_code = main(["checksum", "create", str(batch_dir)])
        out = capsys.readouterr().out
        assert exit_code == EXIT_SUCCESS
        assert "checksum criado" in out
        assert (batch_dir / "SHA256SUMS").exists()

    def test_create_content(self, batch_dir: Path, capsys: pytest.CaptureFixture[str]) -> None:
        main(["checksum", "create", str(batch_dir)])
        capsys.readouterr()
        content = (batch_dir / "SHA256SUMS").read_text(encoding="utf-8")
        a_digest = hashlib.sha256(b"aaa").hexdigest()
        assert a_digest in content
        assert "a.txt" in content

    def test_create_missing_dir_fails(self, tmp_path: Path) -> None:
        missing = tmp_path / "nope"
        exit_code = main(["checksum", "create", str(missing)])
        assert exit_code == EXIT_ERROR


class TestChecksumVerifyCommand:
    def test_verify_ok(self, batch_dir: Path, capsys: pytest.CaptureFixture[str]) -> None:
        main(["checksum", "create", str(batch_dir)])
        capsys.readouterr()
        exit_code = main(["checksum", "verify", str(batch_dir / "SHA256SUMS")])
        out = capsys.readouterr().out
        assert exit_code == EXIT_SUCCESS
        assert "ok" in out

    def test_verify_mismatch(self, batch_dir: Path, capsys: pytest.CaptureFixture[str]) -> None:
        main(["checksum", "create", str(batch_dir)])
        capsys.readouterr()
        # corromper um arquivo → mismatch
        (batch_dir / "a.txt").write_text("changed")
        exit_code = main(["checksum", "verify", str(batch_dir / "SHA256SUMS")])
        out = capsys.readouterr().out
        assert exit_code == EXIT_MISMATCH
        assert "mismatch" in out

    def test_verify_missing_checksum_file(self, tmp_path: Path) -> None:
        missing = tmp_path / "none.sha256"
        exit_code = main(["checksum", "verify", str(missing)])
        assert exit_code == EXIT_ERROR

    def test_verify_invalid_file(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        bad = tmp_path / "bad.sha256"
        bad.write_text("linha inválida\n", encoding="utf-8")
        exit_code = main(["checksum", "verify", str(bad)])
        out = capsys.readouterr().out
        assert exit_code == EXIT_MISMATCH
        assert "invalid" in out
