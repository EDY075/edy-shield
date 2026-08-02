"""Testes da CLI real do EDY Shield (Missão 3)."""

import hashlib
import pathlib

import pytest

from app import __version__
from app.cli.hash_cmd import main


@pytest.fixture()
def sample_file(tmp_path: pytest.TempPathFactory) -> tuple[str, str]:
    """Cria um arquivo temporário e retorna (caminho, digest SHA256)."""
    path = tmp_path / "sample.txt"
    content = b"demo content"
    path.write_bytes(content)
    digest = hashlib.sha256(content).hexdigest()
    return str(path), digest


class TestVersion:
    def test_version_exits_zero(self, capsys: pytest.CaptureFixture[str]) -> None:
        exit_code = main(["--version"])
        out = capsys.readouterr().out
        assert exit_code == 0
        assert __version__ in out


class TestHelp:
    def test_help_exits_zero(self, capsys: pytest.CaptureFixture[str]) -> None:
        exit_code = main(["--help"])
        out = capsys.readouterr().out
        assert exit_code == 0
        assert "hash" in out
        assert "verify" in out


class TestHashCommand:
    def test_hash_prints_digest(
        self, sample_file: tuple[str, str], capsys: pytest.CaptureFixture[str]
    ) -> None:
        path, digest = sample_file
        exit_code = main(["hash", path])
        out = capsys.readouterr().out.strip()
        assert exit_code == 0
        assert out == digest

    def test_hash_missing_file_fails(
        self, tmp_path: pytest.TempPathFactory, capsys: pytest.CaptureFixture[str]
    ) -> None:
        missing = tmp_path / "missing.txt"
        exit_code = main(["hash", str(missing)])
        err = capsys.readouterr().err
        # ARES-QA-029: erro de domínio = exit 2 (EXIT_ERROR)
        assert exit_code == 2
        assert "erro:" in err

    def test_hash_directory_fails(
        self, tmp_path: pytest.TempPathFactory, capsys: pytest.CaptureFixture[str]
    ) -> None:
        exit_code = main(["hash", str(tmp_path)])
        err = capsys.readouterr().err
        # ARES-QA-029: erro de domínio = exit 2 (EXIT_ERROR)
        assert exit_code == 2
        assert "erro:" in err


class TestVerifyCommand:
    def test_verify_ok(
        self, sample_file: tuple[str, str], capsys: pytest.CaptureFixture[str]
    ) -> None:
        path, digest = sample_file
        exit_code = main(["verify", path, "--expected", digest])
        out = capsys.readouterr().out.strip()
        assert exit_code == 0
        assert out == "OK"

    def test_verify_fail(
        self, sample_file: tuple[str, str], capsys: pytest.CaptureFixture[str]
    ) -> None:
        path, _digest = sample_file
        wrong = "0" * 64
        exit_code = main(["verify", path, "--expected", wrong])
        out = capsys.readouterr().out.strip()
        assert exit_code == 1
        assert out == "FAIL"

    def test_verify_missing_file_fails(
        self, tmp_path: pytest.TempPathFactory, capsys: pytest.CaptureFixture[str]
    ) -> None:
        missing = tmp_path / "missing.txt"
        exit_code = main(["verify", str(missing), "--expected", "0" * 64])
        err = capsys.readouterr().err
        # ARES-QA-029: arquivo inexistente = erro de domínio = exit 2
        assert exit_code == 2
        assert "erro:" in err


class TestAlgorithmFlag:
    def test_hash_algorithm_flag(
        self, tmp_path: pytest.TempPathFactory, capsys: pytest.CaptureFixture[str]
    ) -> None:
        path = tmp_path / "md5.txt"
        content = b"x"
        path.write_bytes(content)
        digest = hashlib.md5(content).hexdigest()
        exit_code = main(["hash", str(path), "--algorithm", "MD5"])
        out = capsys.readouterr().out.strip()
        assert exit_code == 0
        assert out == digest


class TestRootFlag:
    def test_hash_outside_root_fails(
        self,
        sample_file: tuple[str, str],
        tmp_path: pytest.TempPathFactory,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        path, _digest = sample_file
        other_root = tmp_path / "other_root"
        other_root.mkdir()
        exit_code = main(["hash", path, "--root", str(other_root)])
        err = capsys.readouterr().err
        # Caminho fora do root permitido → erro de domínio (ARES-QA-029: exit 2)
        assert exit_code == 2
        assert "erro:" in err

    def test_hash_inside_root_ok(
        self, sample_file: tuple[str, str], capsys: pytest.CaptureFixture[str]
    ) -> None:
        path, digest = sample_file
        root = pathlib.Path(path).parent
        exit_code = main(["hash", path, "--root", str(root)])
        out = capsys.readouterr().out.strip()
        assert exit_code == 0
        assert out == digest

    def test_hash_file_without_extension_uses_parent_root(
        self, tmp_path: pytest.TempPathFactory, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Arquivos sem extensão usam o pai resolvido como root (ARES-QA-025)."""
        path = tmp_path / "noext"
        content = b"data"
        path.write_bytes(content)
        import hashlib as _hashlib

        expected = _hashlib.sha256(content).hexdigest()
        exit_code = main(["hash", str(path)])
        out = capsys.readouterr().out.strip()
        assert exit_code == 0
        assert out == expected


class TestEnvRoot:
    def test_allowed_root_env_used_when_no_flag(
        self,
        sample_file: tuple[str, str],
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """EDY_ALLOWED_ROOT é usado como root default (ARES-QA-028)."""
        path, digest = sample_file
        root = pathlib.Path(path).parent
        monkeypatch.setenv("EDY_ALLOWED_ROOT", str(root))
        exit_code = main(["hash", path])
        out = capsys.readouterr().out.strip()
        assert exit_code == 0
        assert out == digest

    def test_allowed_root_env_outside_denied(
        self,
        sample_file: tuple[str, str],
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """EDY_ALLOWED_ROOT restringe arquivos fora dele (ARES-QA-028)."""
        path, _digest = sample_file
        other_root = pathlib.Path(path).parent / "other_root"
        other_root.mkdir(exist_ok=True)
        monkeypatch.setenv("EDY_ALLOWED_ROOT", str(other_root))
        exit_code = main(["hash", path])
        err = capsys.readouterr().err
        # ARES-QA-029: acesso negado = erro de domínio = exit 2
        assert exit_code == 2
        assert "erro:" in err


class TestEnvRobustness:
    def test_invalid_chunk_size_no_traceback(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Env inválido gera erro legível, não traceback (ARES-QA-026)."""
        monkeypatch.setenv("EDY_CHUNK_SIZE", "abc")
        exit_code = main(["--version"])
        err = capsys.readouterr().err
        # ARES-QA-029: env inválido = erro de domínio = exit 2
        assert exit_code == 2
        assert "erro:" in err
        assert "Traceback" not in err
