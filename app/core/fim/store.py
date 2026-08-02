"""FimStore — persistência gerenciada de baselines (Sprint 5 — FIM v2.0).

Persiste :class:`~app.core.fim.models.Baseline` em disco (JSON por
baseline_id) em ``<base_dir>/<baseline_id>.json``, seguindo a disciplina do
:class:`~app.services.history.HistoryStore`:

* Diretório base criado automaticamente.
* IDs com charset seguro (anti path traversal).
* JSON ``ensure_ascii=False``, round-trip validado na leitura.
* É o **ponto de troca** para SQLite na v2.1 sem afetar contratos
  (ADR-FIM-001).

O caminho padrão é ``~/.edyshield/fim``.
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path

from app.core.exceptions import BaselineNotFoundError
from app.core.fim.baseline import load_baseline, save_baseline
from app.core.fim.ids import build_baseline_id
from app.core.fim.models import Baseline

#: Caracteres permitidos no baseline_id (padrão HistoryStore).
_SAFE_ID_RE = re.compile(r"[^A-Za-z0-9_.-]")

#: Diretório padrão das baselines.
DEFAULT_FIM_DIR = Path.home() / ".edyshield" / "fim"


class FimStore:
    """Armazena e consulta baselines em um diretório base.

    Args:
        base_dir: Diretório onde os arquivos JSON serão gravados.
            Criado automaticamente quando não existe.
    """

    def __init__(self, base_dir: Path = DEFAULT_FIM_DIR) -> None:
        self._base_dir = base_dir
        self._base_dir.mkdir(parents=True, exist_ok=True)

    @property
    def base_dir(self) -> Path:
        """Diretório de armazenamento das baselines."""
        return self._base_dir

    @staticmethod
    def build_id(algorithm: str, now: datetime | None = None) -> str:
        """Gerar ``fim_<algo>_<UTC %Y%m%dT%H%M%SZ>``.

        Args:
            algorithm: Algoritmo (ex.: ``SHA256``).
            now: Momento UTC injetável (testes).

        Returns:
            Id no formato canônico (ex.: ``fim_sha256_20260802T120000Z``).
        """
        return build_baseline_id(algorithm, now)

    def save(self, baseline: Baseline) -> str:
        """Persistir a baseline e retornar o ``baseline_id``.

        Args:
            baseline: Baseline a salvar.

        Returns:
            O id da baseline persistida.
        """
        path = self._path_for(baseline.baseline_id)
        save_baseline(baseline, path)
        return baseline.baseline_id

    def load(self, baseline_id: str) -> Baseline:
        """Carregar e validar uma baseline pelo id.

        Args:
            baseline_id: Id retornado por :meth:`save`.

        Returns:
            A baseline persistida.

        Raises:
            BaselineNotFoundError: Se a baseline não existir.
            BaselineCorruptionError: Se o arquivo estiver corrompido.
        """
        path = self._path_for(baseline_id)
        if not path.exists():
            raise BaselineNotFoundError(f"baseline não encontrada: {baseline_id}")
        return load_baseline(path)

    def list(self) -> list[dict[str, object]]:
        """Listar metadados das baselines, do mais recente ao mais antigo.

        Returns:
            Lista de dicionários com ``id``, ``algorithm``, ``root``,
            ``created_at`` e ``entries`` (contagem).
        """
        entries: list[dict[str, object]] = []
        for path in sorted(self._base_dir.glob("*.json"), reverse=True):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                continue
            entries.append(
                {
                    "id": path.stem,
                    "algorithm": data.get("algorithm", "?"),
                    "root": data.get("root", "?"),
                    "created_at": data.get("created_at", "?"),
                    "entries": len(data.get("entries", [])),
                }
            )
        return entries

    def delete(self, baseline_id: str) -> bool:
        """Remover uma baseline.

        Args:
            baseline_id: Id da baseline.

        Returns:
            ``True`` se a baseline existia e foi removida, ``False`` caso
            contrário.
        """
        path = self._path_for(baseline_id)
        if not path.exists():
            return False
        try:
            path.unlink()
        except OSError:
            return False
        return True

    def _path_for(self, baseline_id: str) -> Path:
        """Validar o id e devolver o caminho do arquivo.

        Raises:
            BaselineNotFoundError: Se o id tiver charset inseguro (evita
                path traversal via id).
        """
        if not baseline_id or _SAFE_ID_RE.search(baseline_id):
            raise BaselineNotFoundError(f"baseline_id inválido: {baseline_id!r}")
        return self._base_dir / f"{baseline_id}.json"
