"""Testes E2E da CLI — executa o comando real via subprocess.

Verifica stdout, stderr e exit code exatamente como o usuário digita no
terminal. Usa apenas diretórios temporários e o interpretador Python atual.
"""

from __future__ import annotations

import hashlib
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]

EXIT_SUCCESS = 0
EXIT_MISMATCH = 1
EXIT_ERROR = 2


def run_cli(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    """Executar a CLI real em subprocess e capturar a saída."""
    return subprocess.run(
        [sys.executable, "-m", "app.cli.hash_cmd", *args],
        capture_output=True,
        text=True,
        cwd=str(cwd or REPO_ROOT),
        timeout=60,
        check=False,
    )


class TestVersion:
    def test_version_exit_zero(self) -> None:
        proc = run_cli("--version")
        assert proc.returncode == EXIT_SUCCESS
        assert "edyshield" in proc.stdout.lower() or "1.2" in proc.stdout

    def test_help_exit_zero(self) -> None:
        proc = run_cli("--help")
        assert proc.returncode == EXIT_SUCCESS
        assert "hash" in proc.stdout
        assert "verify" in proc.stdout
        assert "checksum" in proc.stdout


class TestHashCommandE2E:
    def test_hash_file(self, tmp_path: Path) -> None:
        f = tmp_path / "dados.txt"
        f.write_bytes(b"e2e content")
        expected = hashlib.sha256(b"e2e content").hexdigest()

        proc = run_cli("hash", str(f))
        assert proc.returncode == EXIT_SUCCESS
        assert proc.stdout.strip() == expected

    def test_verify_ok(self, tmp_path: Path) -> None:
        f = tmp_path / "dados.txt"
        f.write_bytes(b"e2e content")
        expected = hashlib.sha256(b"e2e content").hexdigest()

        proc = run_cli("verify", str(f), "--expected", expected)
        assert proc.returncode == EXIT_SUCCESS
        assert proc.stdout.strip() == "OK"

    def test_verify_mismatch_exit_1(self, tmp_path: Path) -> None:
        f = tmp_path / "dados.txt"
        f.write_bytes(b"e2e content")

        proc = run_cli("verify", str(f), "--expected", "0" * 64)
        assert proc.returncode == EXIT_MISMATCH
        assert proc.stdout.strip() == "FAIL"

    def test_usage_error_exit_2(self, tmp_path: Path) -> None:
        # --expected ausente → erro de uso
        f = tmp_path / "dados.txt"
        f.write_bytes(b"x")
        proc = run_cli("verify", str(f))
        assert proc.returncode == EXIT_ERROR

    def test_missing_file_exit_2(self, tmp_path: Path) -> None:
        proc = run_cli("hash", str(tmp_path / "nao_existe.txt"))
        assert proc.returncode == EXIT_ERROR


class TestBatchCommandE2E:
    def test_hash_batch_directory(self, tmp_path: Path) -> None:
        (tmp_path / "a.txt").write_text("aaa")
        (tmp_path / "b.txt").write_text("bbb")

        proc = run_cli("hash", "--batch", str(tmp_path))
        assert proc.returncode == EXIT_SUCCESS
        lines = proc.stdout.strip().splitlines()
        assert len(lines) == 2
        for line in lines:
            digest, sep, _name = line.partition("  ")
            assert sep == "  " and len(digest) == 64

    def test_hash_batch_recursive(self, tmp_path: Path) -> None:
        (tmp_path / "top.txt").write_text("top")
        sub = tmp_path / "sub"
        sub.mkdir()
        (sub / "deep.txt").write_text("deep")

        proc = run_cli("hash", "--batch", "--recursive", str(tmp_path))
        assert proc.returncode == EXIT_SUCCESS
        assert "deep.txt" in proc.stdout


class TestChecksumCommandE2E:
    def test_checksum_create_and_verify_ok(self, tmp_path: Path) -> None:
        (tmp_path / "a.txt").write_text("aaa")

        create = run_cli("checksum", "create", str(tmp_path))
        assert create.returncode == EXIT_SUCCESS
        checksum_file = tmp_path / "SHA256SUMS"
        assert checksum_file.exists()

        verify = run_cli("checksum", "verify", str(checksum_file))
        assert verify.returncode == EXIT_SUCCESS
        assert "ok" in verify.stdout

    def test_checksum_verify_mismatch_exit_1(self, tmp_path: Path) -> None:
        (tmp_path / "a.txt").write_text("aaa")
        run_cli("checksum", "create", str(tmp_path))
        (tmp_path / "a.txt").write_text("changed!")

        verify = run_cli("checksum", "verify", str(tmp_path / "SHA256SUMS"))
        assert verify.returncode == EXIT_MISMATCH
        assert "mismatch" in verify.stdout

    def test_checksum_missing_file_exit_2(self, tmp_path: Path) -> None:
        proc = run_cli("checksum", "verify", str(tmp_path / "none.sha256"))
        assert proc.returncode == EXIT_ERROR


class TestWindowsCompatibility:
    @pytest.mark.skipif(os.name != "nt", reason="teste específico de Windows")
    def test_runs_on_windows(self, tmp_path: Path) -> None:
        """A CLI executa e o hash de arquivo funciona no Windows."""
        f = tmp_path / "win.txt"
        f.write_text("windows")
        proc = run_cli("hash", str(f))
        assert proc.returncode == EXIT_SUCCESS
        assert len(proc.stdout.strip()) == 64
