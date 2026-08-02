"""Histórico de varreduras do EDY Shield (Sprint 3, Missão 9; v2.1 M1).

Persiste :class:`ScanResult` para a seção **Histórico** da UI. A UI nunca
acessa o filesystem diretamente — consome este serviço via API (Missão 9).

Backend (v2.1 — M1): **SQLite** via :class:`app.core.storage.SQLiteDb`,
com **compatibilidade retroativa**:

* Contrato público preservado (``save``/``list``/``get``/``clear``).
* ``db_path`` opcional (padrão ``~/.edyshield/edy_shield.db``).
* Migração automática e idempotente de JSON legado → SQLite na inicialização.
* Fallback de leitura: se o id não existe no SQLite, tenta o JSON legado.
"""

from __future__ import annotations

import contextlib
import json
import re
from datetime import UTC
from pathlib import Path

from app.core.storage import DEFAULT_DB_PATH, SQLiteDb
from app.plugins.contracts import ScanResult
from app.plugins.plugin_errors import PluginError

#: Caracteres permitidos no id do histórico (padrão original).
_SAFE_ID_RE = re.compile(r"[^A-Za-z0-9_.-]")


class HistoryError(PluginError):
    """Falha ao persistir/ler o histórico de varreduras."""


class HistoryStore:
    """Armazena e consulta ScanResults em SQLite (com fallback JSON legado).

    Args:
        base_dir: Diretório legado (JSON). Usado para migração automática e
            fallback de leitura; criado automaticamente quando não existe.
        db_path: Caminho do banco SQLite. ``None`` usa o padrão
            (``~/.edyshield/edy_shield.db``).
    """

    def __init__(self, base_dir: Path, db_path: Path | None = None) -> None:
        self._base_dir = base_dir
        self._base_dir.mkdir(parents=True, exist_ok=True)
        self._db = SQLiteDb(db_path if db_path is not None else DEFAULT_DB_PATH)
        self._migrate_from_json()

    @property
    def base_dir(self) -> Path:
        """Diretório legado (JSON) do histórico."""
        return self._base_dir

    @property
    def db_path(self) -> Path:
        """Caminho do banco SQLite usado pelo store."""
        return self._db.db_path

    def save(self, result: ScanResult) -> str:
        """Persistir um resultado e retornar o id gerado.

        Args:
            result: Resultado a salvar.

        Returns:
            O id do registro (usado para consulta e download).
        """
        scan_id = self._build_id(result)
        payload = json.dumps(result.as_dict(), ensure_ascii=False)
        self._db.execute(
            """
            INSERT OR REPLACE INTO scans
                (scan_id, plugin_name, plugin_version, timestamp, max_severity, payload)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                scan_id,
                result.plugin_name,
                result.plugin_version,
                result.timestamp.astimezone(UTC).isoformat(),
                result.max_severity().value,
                payload,
            ),
        )
        return scan_id

    def list(self) -> list[dict[str, object]]:
        """Listar metadados dos registros, do mais recente ao mais antigo.

        Returns:
            Lista de dicionários com ``id``, ``plugin_name``, ``plugin_version``,
            ``timestamp`` e ``max_severity``.
        """
        rows = self._db.query(
            """
            SELECT scan_id, plugin_name, plugin_version, timestamp, max_severity
            FROM scans
            ORDER BY timestamp DESC
            """
        )
        return [
            {
                "id": row["scan_id"],
                "plugin_name": row["plugin_name"],
                "plugin_version": row["plugin_version"],
                "timestamp": row["timestamp"],
                "max_severity": row["max_severity"],
            }
            for row in rows
        ]

    def get(self, scan_id: str) -> ScanResult | None:
        """Carregar um resultado pelo id.

        Consulta o SQLite; se não existir, tenta o JSON legado (backup).

        Args:
            scan_id: Id retornado por :meth:`save`.

        Returns:
            O :class:`ScanResult` persistido, ou ``None`` se não existir.
        """
        self._validate_id(scan_id)
        row = self._db.query_one("SELECT payload FROM scans WHERE scan_id = ?", (scan_id,))
        if row is not None:
            try:
                return ScanResult.from_dict(json.loads(row["payload"]))
            except (json.JSONDecodeError, KeyError, TypeError) as exc:
                raise HistoryError(f"histórico corrompido: {scan_id}") from exc

        # Fallback legado (JSON migrado/backup)
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
            Quantidade de registros removidos (SQLite + JSON legado).
        """
        removed = self._db.execute("DELETE FROM scans")
        for path in self._base_dir.glob("*.json"):
            try:
                path.unlink()
                removed += 1
            except OSError:
                continue
        return removed

    # ------------------------------------------------------------------
    # Migração e helpers internos
    # ------------------------------------------------------------------

    def _migrate_from_json(self) -> None:
        """Migrar JSON legado → SQLite (idempotente) e arquivar os arquivos.

        Só executa quando existem arquivos JSON e a tabela está vazia.
        Após inserir com sucesso, move os JSON para ``<base_dir>/../backup``.
        """
        json_files = sorted(self._base_dir.glob("*.json"))
        if not json_files:
            return
        count = self._db.scalar("SELECT COUNT(*) FROM scans")
        if count:
            return  # já migrado (idempotente)

        rows: list[tuple[str, str, str, str, str, str]] = []
        backup_dir = self._base_dir.parent / "backup" / self._base_dir.name
        for path in json_files:
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                continue
            if not isinstance(data, dict) or "plugin_name" not in data:
                continue
            rows.append(
                (
                    path.stem,
                    str(data.get("plugin_name", "?")),
                    str(data.get("plugin_version", "?")),
                    str(data.get("timestamp", "?")),
                    str(data.get("max_severity", "INFO")),
                    json.dumps(data, ensure_ascii=False),
                )
            )
        if rows:
            self._db.executemany(
                """
                INSERT OR IGNORE INTO scans
                    (scan_id, plugin_name, plugin_version, timestamp, max_severity, payload)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                rows,
            )
        # Arquiva os JSON migrados (backup) — só após sucesso
        backup_dir.mkdir(parents=True, exist_ok=True)
        for path in json_files:
            with contextlib.suppress(OSError):
                path.replace(backup_dir / path.name)

    def _validate_id(self, scan_id: str) -> None:
        """Validar o id (evita path traversal via id da URL).

        Raises:
            HistoryError: Se o id contiver caracteres inseguros.
        """
        if not scan_id or _SAFE_ID_RE.search(scan_id):
            raise HistoryError(f"id de histórico inválido: {scan_id!r}")

    def _build_id(self, result: ScanResult) -> str:
        """Construir um id estável a partir do timestamp e do plugin."""
        stamp = result.timestamp.astimezone(UTC).strftime("%Y%m%dT%H%M%SZ")
        return f"{stamp}_{result.plugin_name}"

    def _path_for(self, scan_id: str) -> Path:
        """Caminho do arquivo JSON legado (fallback/backup)."""
        self._validate_id(scan_id)
        return self._base_dir / f"{scan_id}.json"
