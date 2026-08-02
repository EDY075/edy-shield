"""Análise persistida — modelo e store do Analysis Engine (v2.1 — M2.3).

Camada de dados para o resultado de análises (String/Entropy) com o objetivo
de recuperação/histórico. Complementa o :class:`~app.services.history.HistoryStore`
com campos estruturados para filtragem (plugin, categoria, severidade, data),
além de duração da análise e contagem de evidências.

Backend (v2.1 — M2.3): **SQLite** via :class:`app.core.storage.SQLiteDb`,
tabela ``analyses`` (100% stdlib — ADR-001).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.core.storage import DEFAULT_DB_PATH, SQLiteDb
from app.plugins.contracts import ScanResult
from app.plugins.plugin_errors import PluginError


class AnalysisError(PluginError):
    """Falha ao persistir/ler registros de análise."""


@dataclass(frozen=True, slots=True)
class AnalysisRecord:
    """Registro de análise persistido (visão estruturada do ScanResult).

    Attributes:
        analysis_id: Identificador único do registro.
        target: Alvo analisado (arquivo ou diretório).
        timestamp: Momento da análise (timezone-aware, UTC).
        plugin_name: Plugin que produziu o resultado.
        category: Categoria predominante (ex.: ``url``, ``total``) ou
            ``None`` quando não se aplica.
        severity: Severidade máxima (INFO..CRITICAL).
        score: Pontuação numérica 0-100 (quando aplicável; 0 para String).
        evidence_count: Quantidade de evidências no resultado.
        duration_ms: Duração da análise em milissegundos.
        result: :class:`ScanResult` completo persistido.
    """

    analysis_id: str
    target: str
    timestamp: datetime
    plugin_name: str
    severity: str
    evidence_count: int
    duration_ms: float
    version: str
    category: str | None = None
    score: int = 0
    result: ScanResult | None = None
    metadata: dict[str, str] = field(default_factory=dict)


class AnalysisStore:
    """Persiste e consulta registros de análise em SQLite.

    Args:
        base_dir: Diretório reservado (compatibilidade de interface).
        db_path: Caminho do banco SQLite. ``None`` usa o padrão.
    """

    def __init__(self, base_dir: Path | None = None, db_path: Path | None = None) -> None:
        self._base_dir = base_dir or Path.home() / ".edyshield" / "analyses"
        self._base_dir.mkdir(parents=True, exist_ok=True)
        self._db = SQLiteDb(db_path if db_path is not None else DEFAULT_DB_PATH)

    @property
    def db_path(self) -> Path:
        """Caminho do banco SQLite usado pelo store."""
        return self._db.db_path

    def close(self) -> None:
        """Fechar a conexão SQLite (liberar recursos)."""
        self._db.close()

    def save(self, record: AnalysisRecord) -> str:
        """Persistir um registro de análise e devolver o id."""
        payload = (
            record.result.as_dict()
            if record.result is not None
            else json.dumps(record.metadata, ensure_ascii=False)
        )
        self._db.execute(
            """
            INSERT OR REPLACE INTO analyses
                (analysis_id, target, timestamp, plugin_name, category, severity,
                 score, evidence_count, duration_ms, payload)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record.analysis_id,
                record.target,
                record.timestamp.astimezone(UTC).isoformat(),
                record.plugin_name,
                record.category,
                record.severity,
                record.score,
                record.evidence_count,
                record.duration_ms,
                json.dumps(payload, ensure_ascii=False),
            ),
        )
        return record.analysis_id

    def list(
        self,
        *,
        plugin: str | None = None,
        severity: str | None = None,
        category: str | None = None,
        since: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, object]]:
        """Listar análises com filtros opcionais, da mais recente para a mais antiga.

        Args:
            plugin: Filtrar por ``plugin_name`` (case-insensitive).
            severity: Filtrar por severidade máxima.
            category: Filtrar por categoria.
            since: Filtrar por timestamp >= este valor ISO (inclusive).
            limit: Quantidade máxima de registros (padrão 100).

        Returns:
            Lista ordenada (mais recente primeiro) de metadados.
        """
        conditions: list[str] = []
        params: list[Any] = []
        if plugin:
            conditions.append("plugin_name = ?")
            params.append(plugin)
        if severity:
            conditions.append("severity = ?")
            params.append(severity.upper())
        if category:
            conditions.append("(category = ? OR payload LIKE ?)")
            params.extend([category, f'%"{category}"%'])
        if since:
            conditions.append("timestamp >= ?")
            params.append(since)

        where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
        params.append(limit)
        rows = self._db.query(
            f"""
            SELECT analysis_id, target, timestamp, plugin_name, category, severity,
                   score, evidence_count, duration_ms
            FROM analyses
            {where}
            ORDER BY timestamp DESC
            LIMIT ?
            """,
            tuple(params),
        )
        return [dict(row) for row in rows]

    def get(self, analysis_id: str) -> dict[str, Any] | None:
        """Carregar um registro de análise completo pelo id.

        Args:
            analysis_id: Id retornado por :meth:`save`.

        Returns:
            Metadados + ``payload`` (resultado completo), ou ``None``.
        """
        row = self._db.query_one("SELECT * FROM analyses WHERE analysis_id = ?", (analysis_id,))
        if row is None:
            return None
        out = dict(row)
        try:
            out["payload"] = json.loads(str(row["payload"]))
        except (json.JSONDecodeError, TypeError) as exc:
            raise AnalysisError(f"análise corrompida: {analysis_id}") from exc
        return out

    def clear(self) -> int:
        """Remover todos os registros de análise.

        Returns:
            Quantidade removida.
        """
        return self._db.execute("DELETE FROM analyses")

    @staticmethod
    def build_id(plugin_name: str) -> str:
        """Construir um id estável (timestamp + plugin)."""
        stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%f")
        return f"ana_{stamp}_{plugin_name}"
