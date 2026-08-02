"""Testes da configuração do EDY Shield (Missão 3)."""

import pytest

from app.core.config import Settings, load_settings


class TestSettingsDefaults:
    """Valores padrão da configuração."""

    def test_defaults(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("EDY_DEFAULT_HASH_ALGORITHM", raising=False)
        monkeypatch.delenv("EDY_LOG_LEVEL", raising=False)
        monkeypatch.delenv("EDY_CHUNK_SIZE", raising=False)
        monkeypatch.delenv("EDY_ALLOWED_ROOT", raising=False)
        monkeypatch.delenv("EDY_TEXT_ENCODING", raising=False)

        settings = load_settings()

        assert settings.default_hash_algorithm == "SHA256"
        assert settings.log_level == "INFO"
        assert settings.allowed_root is None
        assert settings.chunk_size == 65536
        assert settings.encoding == "utf-8"

    def test_frozen_dataclass(self) -> None:
        settings = Settings()
        with pytest.raises(AttributeError):
            settings.default_hash_algorithm = "MD5"  # type: ignore[misc]


class TestSettingsEnvironment:
    """Override via variáveis de ambiente EDY_*."""

    def test_algorithm_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("EDY_DEFAULT_HASH_ALGORITHM", "SHA1")
        assert load_settings().default_hash_algorithm == "SHA1"

    def test_log_level_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("EDY_LOG_LEVEL", "DEBUG")
        assert load_settings().log_level == "DEBUG"

    def test_chunk_size_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("EDY_CHUNK_SIZE", "4096")
        assert load_settings().chunk_size == 4096

    def test_allowed_root_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("EDY_ALLOWED_ROOT", r"C:\tmp\root")
        settings = load_settings()
        assert settings.allowed_root is not None
        assert str(settings.allowed_root) == r"C:\tmp\root"

    def test_encoding_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("EDY_TEXT_ENCODING", "latin-1")
        assert load_settings().encoding == "latin-1"


class TestSettingsValidation:
    """Erros de validação da configuração."""

    def test_invalid_chunk_size_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("EDY_CHUNK_SIZE", "abc")
        with pytest.raises(ValueError, match="must be an integer"):
            load_settings()

    def test_non_positive_chunk_size_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("EDY_CHUNK_SIZE", "0")
        with pytest.raises(ValueError, match="positive integer"):
            load_settings()
