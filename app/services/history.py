"""Histórico de varreduras do EDY Shield (Sprint 3, Missão 9).

Persiste :class:`ScanResult` em disco (JSON por execução) para a seção
**Histórico** da UI. A UI nunca acessa o filesystem diretamente — consome
este serviço via API (Missão 9).

Formato de armazenamento:

    <base_dir>/<scan_id>.json

Onde ``scan_id`` é um carimbo UTC + plugin (ex.:
``20260801T120000Z_log_analyzer``). Cada arquivo contém o dicionário
produzido por :meth:`ScanResult.as_dict`.
"""

from __future__ import annotations

import json
import re
from datetime import UTC
from pathlib import Path

from app.plugins.contracts import ScanResult
from app.plugins.plugin_errors import PluginError

#: Caracteres permitidos no nome do arquivo de histórico.
_SAFE_ID_RE = re.compile(r"[^A-Za-z0-9_.-]")


class HistoryError(PluginError):
    """Falha ao persistir/ler o histórico de varreduras."""


class HistoryStore:
    """Armazena e consulta ScanResults em um diretório base.

    Args:
        base_dir: Diretório onde os arquivos JSON serão gravados.
            Criado automaticamente quando não existe.
    """

    def __init__(self, base_dir: Path) -> None:
        self._base_dir = base_dir
        self._base_dir.mkdir(parents=True, exist_ok=True)

    @property
    def base_dir(self) -> Path:
        """Diretório de armazenamento do histórico."""
        return self._base_dir

    def save(self, result: ScanResult) -> str:
        """Persistir um resultado e retornar o id gerado.

        Args:
            result: Resultado a salvar.

        Returns:
            O id do registro (usado para consulta e download).
        """
        scan_id = self._build_id(result)
        path = self._path_for(scan_id)
        path.write_text(
            json.dumps(result.as_dict(), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        return scan_id

    def list(self) -> list[dict[str, object]]:
        """Listar metadados dos registros, do mais recente ao mais antigo.

        Returns:
            Lista de dicionários com ``id``, ``plugin_name``, ``plugin_version``,
            ``timestamp`` e ``max_severity``.
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
                    "plugin_name": data.get("plugin_name", "?"),
                    "plugin_version": data.get("plugin_version", "?"),
                    "timestamp": data.get("timestamp", "?"),
                    "max_severity": data.get("max_severity", "INFO"),
                }
            )
        return entries

    def get(self, scan_id: str) -> ScanResult | None:
        """Carregar um resultado pelo id.

        Args:
            scan_id: Id retornado por :meth:`save`.

        Returns:
            O :class:`ScanResult` persistido, ou ``None`` se não existir.
        """
        path = self._path_for(scan_id)
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            raise HistoryError(f"histórico corrompido: {scan_id}") from exc
        return ScanResult.from_dict(data)

    def clear(self) -> int:
        """Remover todos os registros do histórico.

        Returns:
            Quantidade de arquivos removidos.
        """
        removed = 0
        for path in self._base_dir.glob("*.json"):
            try:
                path.unlink()
                removed += 1
            except OSError:
                continue
        return removed

    def _build_id(self, result: ScanResult) -> str:
        """Construir um id estável a partir do timestamp e do plugin."""
        stamp = result.timestamp.astimezone(UTC).strftime("%Y%m%dT%H%M%SZ")
        return f"{stamp}_{result.plugin_name}"

    def _path_for(self, scan_id: str) -> Path:
        """Validar o id e devolver o caminho do arquivo.

        Raises:
            HistoryError: Se o id contiver caracteres inseguros (evita
                path traversal via id da URL).
        """
        if not scan_id or _SAFE_ID_RE.search(scan_id):
            raise HistoryError(f"id de histórico inválido: {scan_id!r}")
        return self._base_dir / f"{scan_id}.json"
