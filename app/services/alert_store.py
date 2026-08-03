"""Persistencia de alertas em SQLite (EDY Shield -- M3-T07).

Camada de dados do Alert Engine: persiste
:class:`~app.core.alerts.models.AlertRecord` na tabela ``alerts`` do
banco SQLite unificado. Segue o mesmo padrao arquitetural do
:class:`~app.services.analysis_store.AnalysisStore` (ADR-001).

Backend: :class:`~app.core.storage.SQLiteDb` (100% stdlib sqlite3).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.core.alerts.models import AlertRecord, AlertStatus, Severity
from app.core.storage import DEFAULT_DB_PATH, SQLiteDb
from app.plugins.plugin_errors import PluginError

__all__ = ["AlertComment", "AlertStore", "AlertStoreError"]


class AlertStoreError(PluginError):
    """Falha ao persistir/ler registros de alerta."""


@dataclass(slots=True)
class AlertComment:
    """Comentário de investigação de um alerta."""

    id: int
    alert_id: str
    author: str
    body: str
    created_at: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "alert_id": self.alert_id,
            "author": self.author,
            "body": self.body,
            "created_at": self.created_at,
        }


class AlertStore:
    """Persiste e consulta alertas em SQLite.

    Args:
        db_path: Caminho do banco SQLite. ``None`` usa o padrao
            (:attr:`~app.core.storage.DEFAULT_DB_PATH`).
    """

    def __init__(self, db_path: Path | None = None) -> None:
        self._db = SQLiteDb(db_path if db_path is not None else DEFAULT_DB_PATH)

    @property
    def db_path(self) -> Path:
        """Caminho do banco SQLite usado pelo store."""
        return self._db.db_path

    def close(self) -> None:
        """Fechar a conexao SQLite (liberar recursos)."""
        self._db.close()

    def save(self, record: AlertRecord) -> str:
        """Persistir ou atualizar um alerta (INSERT OR REPLACE).

        Args:
            record: Alerta a persistir.

        Returns:
            ``alert_id`` do alerta persistido.
        """
        details_json = json.dumps(record.details, ensure_ascii=False, default=str)
        self._db.execute(
            """
            INSERT OR REPLACE INTO alerts
                (alert_id, fingerprint, title, description, source, rule_id,
                 severity, status, target, count, first_seen_at, last_seen_at,
                 details, acknowledged_at, acknowledged_by, resolved_at,
                 resolved_by, resolution_note)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record.alert_id,
                record.fingerprint,
                record.title,
                record.description,
                record.source,
                record.rule_id,
                record.severity.value,
                record.status.value,
                record.target,
                record.count,
                record.first_seen_at,
                record.last_seen_at,
                details_json,
                record.acknowledged_at,
                record.acknowledged_by,
                record.resolved_at,
                record.resolved_by,
                record.resolution_note,
            ),
        )
        return record.alert_id

    def get(self, alert_id: str) -> AlertRecord | None:
        """Carregar um alerta completo pelo ID.

        Args:
            alert_id: ID do alerta.

        Returns:
            :class:`AlertRecord` se encontrado, ``None`` caso contrario.
        """
        row = self._db.query_one(
            "SELECT * FROM alerts WHERE alert_id = ?",
            (alert_id,),
        )
        if row is None:
            return None
        return AlertRecord.from_dict(row)

    def get_by_fingerprint_active(self, fingerprint: str) -> AlertRecord | None:
        """Buscar alerta ativo (NEW ou ACKNOWLEDGED) por fingerprint.

        Usado pelo service para hidratar o cache de dedup na inicializacao
        e verificar se um alerta ja existe antes de criar um novo.

        Args:
            fingerprint: Hash SHA-256 do alerta.

        Returns:
            :class:`AlertRecord` se existir alerta ativo, ``None`` caso contrario.
        """
        row = self._db.query_one(
            """
            SELECT * FROM alerts
            WHERE fingerprint = ?
              AND status IN ('NEW', 'ACKNOWLEDGED')
            ORDER BY last_seen_at DESC
            LIMIT 1
            """,
            (fingerprint,),
        )
        if row is None:
            return None
        return AlertRecord.from_dict(row)

    def list_alerts(
        self,
        *,
        severity: Severity | None = None,
        status: AlertStatus | None = None,
        source: str | None = None,
        rule_id: str | None = None,
        since: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[AlertRecord]:
        """Listar alertas com filtros opcionais, paginacao e ordenacao.

        Args:
            severity: Filtrar por severidade.
            status: Filtrar por status.
            source: Filtrar por origem.
            rule_id: Filtrar por ID de regra.
            since: Filtrar por ``last_seen_at >=`` este timestamp ISO.
            limit: Quantidade maxima (default 50).
            offset: Deslocamento para paginacao (default 0).

        Returns:
            Lista ordenada por ``last_seen_at DESC`` (mais recente primeiro).
        """
        conditions: list[str] = []
        params: list[Any] = []
        if severity is not None:
            conditions.append("severity = ?")
            params.append(severity.value)
        if status is not None:
            conditions.append("status = ?")
            params.append(status.value)
        if source:
            conditions.append("source = ?")
            params.append(source)
        if rule_id:
            conditions.append("rule_id = ?")
            params.append(rule_id)
        if since:
            conditions.append("last_seen_at >= ?")
            params.append(since)

        where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
        params.extend([limit, offset])
        rows = self._db.query(
            f"""
            SELECT * FROM alerts
            {where}
            ORDER BY last_seen_at DESC
            LIMIT ? OFFSET ?
            """,
            tuple(params),
        )
        return [AlertRecord.from_dict(row) for row in rows]

    def update_status(
        self,
        alert_id: str,
        status: AlertStatus,
        *,
        acknowledged_at: str | None = None,
        acknowledged_by: str | None = None,
        resolved_at: str | None = None,
        resolved_by: str | None = None,
        resolution_note: str | None = None,
    ) -> bool:
        """Atualizar status e campos de auditoria de um alerta.

        Args:
            alert_id: ID do alerta a atualizar.
            status: Novo status.
            acknowledged_at: Timestamp de_ack (se aplicavel).
            acknowledged_by:Usuario que ack (se aplicavel).
            resolved_at: Timestamp de resolucao (se aplicavel).
            resolved_by: Usuario que resolveu (se aplicavel).
            resolution_note: Nota de resolucao (se aplicavel).

        Returns:
            ``True`` se atualizado, ``False`` se alerta nao encontrado.
        """
        # Buscar registro atual para preservar campos nao atualizados
        existing = self.get(alert_id)
        if existing is None:
            return False
        existing.status = status
        if acknowledged_at is not None:
            existing.acknowledged_at = acknowledged_at
        if acknowledged_by is not None:
            existing.acknowledged_by = acknowledged_by
        if resolved_at is not None:
            existing.resolved_at = resolved_at
        if resolved_by is not None:
            existing.resolved_by = resolved_by
        if resolution_note is not None:
            existing.resolution_note = resolution_note
        self.save(existing)
        return True

    def update_count(self, alert_id: str, count: int, last_seen_at: str) -> bool:
        """Atualizar contador e last_seen de um alerta deduplicado (UPDATE otimizado).

        Args:
            alert_id: ID do alerta.
            count: Novo contador.
            last_seen_at: Novo timestamp.

        Returns:
            ``True`` se atualizado, ``False`` se nao encontrado.
        """
        affected = self._db.execute(
            "UPDATE alerts SET count = ?, last_seen_at = ? WHERE alert_id = ?",
            (count, last_seen_at, alert_id),
        )
        return affected > 0

    def stats(self) -> dict[str, Any]:
        """Retornar estatisticas agregadas dos alertas.

        Returns:
            Dicionario com contagem por status, por severidade e total.
        """
        total = self._db.scalar("SELECT COUNT(*) FROM alerts") or 0
        by_status_rows = self._db.query(
            "SELECT status, COUNT(*) as cnt FROM alerts GROUP BY status"
        )
        by_severity_rows = self._db.query(
            "SELECT severity, COUNT(*) as cnt FROM alerts GROUP BY severity"
        )
        by_source_rows = self._db.query(
            "SELECT source, COUNT(*) as cnt FROM alerts GROUP BY source"
        )
        return {
            "total": int(total),
            "by_status": {row["status"]: int(row["cnt"]) for row in by_status_rows},
            "by_severity": {row["severity"]: int(row["cnt"]) for row in by_severity_rows},
            "by_source": {row["source"]: int(row["cnt"]) for row in by_source_rows},
        }

    def clear(self) -> int:
        """Remover todos os alertas.

        Returns:
            Quantidade removida.
        """
        return self._db.execute("DELETE FROM alerts")

    def count(self) -> int:
        """Retornar total de alertas persistidos."""
        result = self._db.scalar("SELECT COUNT(*) FROM alerts")
        return int(result) if result is not None else 0

    # --- Comentários de Investigação (M4.4) ---

    def add_comment(self, alert_id: str, author: str, body: str) -> AlertComment:
        """Adicionar comentário a um alerta.

        Args:
            alert_id: ID do alerta.
            author: Autor do comentário.
            body: Conteúdo do comentário.

        Returns:
            :class:`AlertComment` criado.
        """
        from datetime import UTC, datetime

        created_at = datetime.now(UTC).isoformat()
        self._db.execute(
            "INSERT INTO alert_comments (alert_id, author, body, created_at) VALUES (?, ?, ?, ?)",
            (alert_id, author, body, created_at),
        )
        row = self._db.query_one(
            "SELECT id, alert_id, author, body, created_at FROM alert_comments WHERE id = last_insert_rowid()",
            (),
        )
        assert row is not None  # recém-inserido
        return AlertComment(
            id=int(row["id"]),
            alert_id=str(row["alert_id"]),
            author=str(row["author"]),
            body=str(row["body"]),
            created_at=str(row["created_at"]),
        )

    def get_comments(self, alert_id: str) -> list[AlertComment]:
        """Listar comentários de um alerta (ordenados por criação)."""
        rows = self._db.query(
            "SELECT id, alert_id, author, body, created_at FROM alert_comments WHERE alert_id = ? ORDER BY created_at ASC",
            (alert_id,),
        )
        return [
            AlertComment(
                id=int(r["id"]),
                alert_id=str(r["alert_id"]),
                author=str(r["author"]),
                body=str(r["body"]),
                created_at=str(r["created_at"]),
            )
            for r in rows
        ]

    # --- Alertas Semelhantes (por fingerprint) ---

    def get_by_fingerprint(self, fingerprint: str, exclude_id: str | None = None) -> list[AlertRecord]:
        """Buscar alertas com o mesmo fingerprint (eventos correlacionados).

        Args:
            fingerprint: Fingerprint SHA-256.
            exclude_id: ID a excluir da lista (opcional).

        Returns:
            Lista de alertas com o mesmo fingerprint.
        """
        if exclude_id:
            rows = self._db.query(
                "SELECT * FROM alerts WHERE fingerprint = ? AND alert_id != ? ORDER BY last_seen_at DESC",
                (fingerprint, exclude_id),
            )
        else:
            rows = self._db.query(
                "SELECT * FROM alerts WHERE fingerprint = ? ORDER BY last_seen_at DESC",
                (fingerprint,),
            )
        return [AlertRecord.from_dict(row) for row in rows]

    def get_ioc_fields(self, alert_id: str) -> dict[str, str]:
        """Extrair campos de investigação (IOC-like) dos detalhes de um alerta.

        Retorna dicionário com chaves canônicas: ip, domain, hash, file, process, user.
        """
        record = self.get(alert_id)
        if record is None:
            return {}
        details = record.details or {}
        return {
            "ip": details.get("ip", ""),
            "domain": details.get("domain", ""),
            "hash": details.get("hash", ""),
            "file": record.target,
            "process": details.get("process", ""),
            "user": details.get("user", ""),
        }
