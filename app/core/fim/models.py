"""Modelos de domínio do File Integrity Monitor (Sprint 5 — FIM v2.0).

Tipos compartilhados do FIM, seguindo o padrão ADR-006 (módulo puro no
Core, 100% stdlib):

* :class:`ChangeType` — tipos de mudança detectados por uma comparação.
* :class:`BaselineEntry` — entrada de integridade de um arquivo.
* :class:`Baseline` — snapshot persistido (fotografia criptográfica).
* :class:`Snapshot` — varredura efêmera em memória.
* :class:`FimDiff` — diferença baseline x snapshot.

Convenções (ADR-FIM-001/002/003):

* ``path`` é **relativo** à raiz do alvo, em POSIX (``/``), determinístico.
* ``hexdigest`` (digest criptográfico) é a **fonte de verdade**; ``size_bytes``
  e ``mtime_iso`` são triagem/diagnóstico (ADR-FIM-002).
* Dataclasses ``frozen=True, slots=True`` — imutáveis e sem overhead.
* Todos os dataclasses possuem ``to_dict``/``from_dict`` para persistência
  JSON com round-trip validado (ADR-FIM-001).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ChangeType(Enum):
    """Tipo de mudança detectado (ordem canônica)."""

    ADDED = "added"
    MODIFIED = "modified"
    REMOVED = "removed"
    UNCHANGED = "unchanged"


@dataclass(frozen=True, slots=True)
class BaselineEntry:
    """Entrada de integridade de um arquivo.

    Attributes:
        path: Caminho relativo ao alvo, POSIX (``/``) e sem ``..``.
        hexdigest: Digest criptográfico (lowercase) — fonte de verdade.
        size_bytes: Tamanho em bytes no momento da varredura.
        mtime_iso: ``mtime`` em ISO 8601 UTC — triagem/diagnóstico.
        permissions: Modo de permissões em octal (ex.: ``"644"``) quando
            disponível; ``None`` quando o filesystem não expõe (opcional).
    """

    path: str
    hexdigest: str
    size_bytes: int
    mtime_iso: str
    permissions: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serializar a entrada para JSON-friendly dict (ordem canônica)."""
        data: dict[str, Any] = {
            "path": self.path,
            "hexdigest": self.hexdigest,
            "size_bytes": self.size_bytes,
            "mtime_iso": self.mtime_iso,
        }
        if self.permissions is not None:
            data["permissions"] = self.permissions
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> BaselineEntry:
        """Reconstruir uma entrada a partir de ``to_dict()``.

        Raises:
            KeyError/TypeError: Quando campos essenciais estão ausentes ou
                com tipos errados — o chamador (validação de round-trip)
                converte em :class:`BaselineCorruptionError`.
        """
        permissions = data.get("permissions")
        return cls(
            path=str(data["path"]),
            hexdigest=str(data["hexdigest"]),
            size_bytes=int(data["size_bytes"]),
            mtime_iso=str(data["mtime_iso"]),
            permissions=str(permissions) if permissions is not None else None,
        )


@dataclass(frozen=True, slots=True)
class Baseline:
    """Snapshot persistido com metadados e entradas ordenadas.

    Attributes:
        baseline_id: Identificador único (ex.: ``fim_sha256_20260802T120000Z``).
        algorithm: Algoritmo usado (ex.: ``SHA256``) — whitelist do Core.
        version: Versão do formato (atualmente ``1``).
        created_at: Momento da criação em ISO 8601 UTC.
        root: Caminho absoluto do alvo fotografado.
        entries: Entradas de integridade, ordenadas por ``path``.
    """

    baseline_id: str
    algorithm: str
    version: int = 1
    created_at: str = ""
    root: str = ""
    entries: tuple[BaselineEntry, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        """Serializar a baseline para JSON-friendly dict (ordem canônica)."""
        return {
            "version": self.version,
            "baseline_id": self.baseline_id,
            "algorithm": self.algorithm,
            "created_at": self.created_at,
            "root": self.root,
            "entries": [entry.to_dict() for entry in self.entries],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Baseline:
        """Reconstruir uma baseline a partir de ``to_dict()``.

        Raises:
            KeyError/TypeError: Quando campos essenciais estão ausentes ou
                com tipos errados — o chamador (validação de round-trip)
                converte em :class:`BaselineCorruptionError`.
        """
        entries = tuple(BaselineEntry.from_dict(entry) for entry in data.get("entries", []))
        return cls(
            baseline_id=str(data["baseline_id"]),
            algorithm=str(data["algorithm"]),
            version=int(data["version"]),
            created_at=str(data["created_at"]),
            root=str(data["root"]),
            entries=entries,
        )


@dataclass(frozen=True, slots=True)
class Snapshot:
    """Varredura efêmera (memória) de um alvo.

    Attributes:
        root: Caminho absoluto do alvo varrido.
        algorithm: Algoritmo usado na varredura.
        created_at: Momento da varredura em ISO 8601 UTC.
        entries: Entradas de integridade, ordenadas por ``path``.
        ignored: Caminhos relativos ignorados (ex.: symlinks — ADR-FIM-003).
    """

    root: str
    algorithm: str
    created_at: str
    entries: tuple[BaselineEntry, ...] = field(default_factory=tuple)
    ignored: tuple[str, ...] = field(default_factory=tuple)

    @classmethod
    def from_baseline(cls, baseline: Baseline) -> Snapshot:
        """Converter uma Baseline persistida em Snapshot (para ``compare``).

        Permite comparar duas baselines entre si sem re-varrer o disco
        (fluxo ``compare`` da spec — útil para auditar antes/depois).

        Args:
            baseline: Baseline persistida.

        Returns:
            Snapshot com os mesmos metadados e entradas da baseline.
        """
        return cls(
            root=baseline.root,
            algorithm=baseline.algorithm,
            created_at=baseline.created_at,
            entries=baseline.entries,
        )


@dataclass(frozen=True, slots=True)
class FimDiff:
    """Diferença baseline x snapshot.

    Attributes:
        baseline_id: Id da baseline usada como referência.
        algorithm: Algoritmo da comparação.
        scanned_at: Momento da comparação em ISO 8601 UTC.
        added: Paths presentes apenas na snapshot (arquivos novos).
        modified: Paths com digest diferente (arquivos alterados).
        removed: Paths presentes apenas na baseline (arquivos removidos).
        unchanged: Paths com digest idêntico (inalterados).
        ignored: Paths ignorados durante a varredura (ex.: symlinks).
    """

    baseline_id: str
    algorithm: str
    scanned_at: str
    added: tuple[str, ...] = field(default_factory=tuple)
    modified: tuple[str, ...] = field(default_factory=tuple)
    removed: tuple[str, ...] = field(default_factory=tuple)
    unchanged: tuple[str, ...] = field(default_factory=tuple)
    ignored: tuple[str, ...] = field(default_factory=tuple)

    @property
    def changed(self) -> int:
        """Total de mudanças (added + modified + removed)."""
        return len(self.added) + len(self.modified) + len(self.removed)

    def to_dict(self) -> dict[str, Any]:
        """Serializar o diff para JSON-friendly dict."""
        return {
            "baseline_id": self.baseline_id,
            "algorithm": self.algorithm,
            "scanned_at": self.scanned_at,
            "added": list(self.added),
            "modified": list(self.modified),
            "removed": list(self.removed),
            "unchanged": list(self.unchanged),
            "ignored": list(self.ignored),
            "changed": self.changed,
        }
