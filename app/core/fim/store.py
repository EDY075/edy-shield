"""FimStore — persistência gerenciada de baselines (Sprint 5; v2.1 M1).

Persiste :class:`~app.core.fim.models.Baseline` no **SQLite** via
:class:`app.core.storage.SQLiteDb`, com **compatibilidade retroativa**:

* Contrato público preservado (``save``/``load``/``list``/``delete``/``build_id``).
* ``db_path`` opcional (padrão ``~/.edyshield/edy_shield.db``).
* Migração automática e idempotente de JSON legado → SQLite.
* Fallback de leitura: se o id não existe no SQLite, tenta o JSON legado.
* **ARES-QA-033 resolvido**: colisão de ``baseline_id`` no mesmo segundo agora
  gera id único com fração de microsegundos (sem sobrescrever a anterior).

O caminho padrão do diretório legado é ``~/.edyshield/fim``.
"""

from __future__ import annotations

import contextlib
import re
from datetime import datetime
from pathlib import Path

from app.core.exceptions import BaselineCorruptionError, BaselineNotFoundError
from app.core.fim.baseline import load_baseline
from app.core.fim.ids import build_baseline_id, build_unique_baseline_id
from app.core.fim.models import Baseline, BaselineEntry
from app.core.storage import DEFAULT_DB_PATH, SQLiteDb

#: Caracteres permitidos no baseline_id (padrão HistoryStore).
_SAFE_ID_RE = re.compile(r"[^A-Za-z0-9_.-]")

#: Diretório padrão das baselines (legado JSON).
DEFAULT_FIM_DIR = Path.home() / ".edyshield" / "fim"


class FimStore:
    """Armazena e consulta baselines em SQLite (com fallback JSON legado).

    Args:
        base_dir: Diretório legado (JSON). Usado para migração automática e
            fallback de leitura; criado automaticamente quando não existe.
        db_path: Caminho do banco SQLite. ``None`` usa o padrão
            (``~/.edyshield/edy_shield.db``).
    """

    def __init__(self, base_dir: Path = DEFAULT_FIM_DIR, db_path: Path | None = None) -> None:
        self._base_dir = base_dir
        self._base_dir.mkdir(parents=True, exist_ok=True)
        self._db = SQLiteDb(db_path if db_path is not None else DEFAULT_DB_PATH)
        self._migrate_from_json()

    @property
    def base_dir(self) -> Path:
        """Diretório legado (JSON) das baselines."""
        return self._base_dir

    @property
    def db_path(self) -> Path:
        """Caminho do banco SQLite usado pelo store."""
        return self._db.db_path

    def close(self) -> None:
        """Fechar a conexão SQLite (liberar recursos)."""
        self._db.close()

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

        Garante unicidade (ARES-QA-033): se o id já existe no banco (colisão
        de mesmo segundo), gera um id único com fração de microsegundos e
        persiste com o novo id.

        Args:
            baseline: Baseline a salvar.

        Returns:
            O id efetivamente persistido.
        """
        baseline_id = self._unique_or_new(baseline.baseline_id, baseline.algorithm)
        operations: list[tuple[str, tuple[object, ...]]] = [
            (
                """
                INSERT OR REPLACE INTO baselines
                    (baseline_id, algorithm, version, created_at, root)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    baseline_id,
                    baseline.algorithm,
                    baseline.version,
                    baseline.created_at,
                    baseline.root,
                ),
            ),
            ("DELETE FROM baseline_entries WHERE baseline_id = ?", (baseline_id,)),
        ]
        for entry in baseline.entries:
            operations.append(
                (
                    """
                    INSERT INTO baseline_entries
                        (baseline_id, path, hexdigest, size_bytes, mtime_iso, permissions)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        baseline_id,
                        entry.path,
                        entry.hexdigest,
                        entry.size_bytes,
                        entry.mtime_iso,
                        entry.permissions,
                    ),
                )
            )
        self._db.transaction(operations)
        return baseline_id

    def load(self, baseline_id: str) -> Baseline:
        """Carregar e validar uma baseline pelo id.

        Consulta o SQLite; se não existir, tenta o JSON legado (backup).

        Args:
            baseline_id: Id retornado por :meth:`save`.

        Returns:
            A baseline persistida.

        Raises:
            BaselineNotFoundError: Se a baseline não existir.
            BaselineCorruptionError: Se os dados estiverem corrompidos.
        """
        self._validate_id(baseline_id)
        row = self._db.query_one(
            "SELECT algorithm, version, created_at, root FROM baselines WHERE baseline_id = ?",
            (baseline_id,),
        )
        if row is not None:
            entries = self._db.query(
                """
                SELECT path, hexdigest, size_bytes, mtime_iso, permissions
                FROM baseline_entries WHERE baseline_id = ?
                ORDER BY path
                """,
                (baseline_id,),
            )
            baseline = Baseline(
                baseline_id=baseline_id,
                algorithm=row["algorithm"],
                version=row["version"],
                created_at=row["created_at"],
                root=row["root"],
                entries=tuple(
                    BaselineEntry(
                        path=entry["path"],
                        hexdigest=entry["hexdigest"],
                        size_bytes=entry["size_bytes"],
                        mtime_iso=entry["mtime_iso"],
                        permissions=entry["permissions"],
                    )
                    for entry in entries
                ),
            )
            # Validação de round-trip (mesma disciplina do JSON)
            from app.core.fim.baseline import _round_trip_validate

            _round_trip_validate(baseline)
            return baseline

        # Fallback legado (JSON migrado/backup)
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
        rows = self._db.query(
            """
            SELECT b.baseline_id, b.algorithm, b.root, b.created_at,
                   COUNT(e.path) AS entries
            FROM baselines b
            LEFT JOIN baseline_entries e ON e.baseline_id = b.baseline_id
            GROUP BY b.baseline_id
            ORDER BY b.created_at DESC
            """
        )
        return [
            {
                "id": row["baseline_id"],
                "algorithm": row["algorithm"],
                "root": row["root"],
                "created_at": row["created_at"],
                "entries": row["entries"] or 0,
            }
            for row in rows
        ]

    def delete(self, baseline_id: str) -> bool:
        """Remover uma baseline (entradas removidas em cascata).

        Args:
            baseline_id: Id da baseline.

        Returns:
            ``True`` se a baseline existia e foi removida, ``False`` caso
            contrário.
        """
        self._validate_id(baseline_id)
        removed = self._db.execute("DELETE FROM baselines WHERE baseline_id = ?", (baseline_id,))
        if removed:
            return True
        # Fallback legado
        path = self._path_for(baseline_id)
        if path.exists():
            try:
                path.unlink()
                return True
            except OSError:
                return False
        return False

    # ------------------------------------------------------------------
    # Migração e helpers internos
    # ------------------------------------------------------------------

    def _migrate_from_json(self) -> None:
        """Migrar JSON legado → SQLite (idempotente) e arquivar os arquivos."""
        json_files = sorted(self._base_dir.glob("*.json"))
        if not json_files:
            return
        count = self._db.scalar("SELECT COUNT(*) FROM baselines")
        if count:
            return  # já migrado (idempotente)

        backup_dir = self._base_dir.parent / "backup" / self._base_dir.name
        for path in json_files:
            try:
                baseline = load_baseline(path)
            except (BaselineCorruptionError, FileNotFoundError):
                continue
            self.save(baseline)

        backup_dir.mkdir(parents=True, exist_ok=True)
        for path in json_files:
            with contextlib.suppress(OSError):
                path.replace(backup_dir / path.name)

    def _unique_or_new(self, baseline_id: str, algorithm: str) -> str:
        """Retornar o id se livre; senão gerar id único com fração.

        Raises:
            BaselineNotFoundError: Se o id tiver charset inseguro.
        """
        self._validate_id(baseline_id)
        exists = self._db.query_one(
            "SELECT 1 AS x FROM baselines WHERE baseline_id = ?", (baseline_id,)
        )
        if exists is None:
            return baseline_id
        return build_unique_baseline_id(algorithm)

    def _validate_id(self, baseline_id: str) -> None:
        """Validar o id (evita path traversal via id).

        Raises:
            BaselineNotFoundError: Se o id tiver charset inseguro.
        """
        if not baseline_id or _SAFE_ID_RE.search(baseline_id):
            raise BaselineNotFoundError(f"baseline_id inválido: {baseline_id!r}")

    def _path_for(self, baseline_id: str) -> Path:
        """Caminho do arquivo JSON legado (fallback/backup)."""
        self._validate_id(baseline_id)
        return self._base_dir / f"{baseline_id}.json"
