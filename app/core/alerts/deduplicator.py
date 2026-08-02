"""Deduplicacao de alertas por fingerprint temporal (EDY Shield -- M3-T02).

Implementa o algoritmo de deduplicacao descrito no ADR-010: eventos com
mesmo ``fingerprint = SHA256(source + rule_id + target)`` sao agregados
em uma unica instancia de :class:`~app.core.alerts.models.AlertRecord`
dentro de uma janela temporal configuravel.

Logica principal:

* :func:`try_dedup` -- testa se um evento ja existe em cache, atualizando
  contador se dentro da janela.
* :class:`DedupCache` -- cache thread-safe em memoria (dict com RLock) para
  estado ativo de dedup (evita consulta SQLite a cada evento).
* :func:`is_within_window` -- verificacao temporal simples (string ISO).

Uso:

    cache = DedupCache()
    existing = cache.lookup(fingerprint)
    if existing and is_within_window(existing.last_seen_at, window_seconds):
        cache.increment(existing)  # count += 1, last_seen_at = now
    else:
        cache.remember(record)     # novo alerta
"""

from __future__ import annotations

import threading
from dataclasses import dataclass
from datetime import datetime

from app.core.alerts.models import AlertRecord, compute_fingerprint, now_iso

__all__ = [
    "DedupCache",
    "DedupResult",
    "compute_fingerprint",
    "is_within_window",
    "try_dedup",
]


#: Formato ISO-8601 usado por todos os timestamps do EDY Shield.
_ISO_FORMAT = "%Y-%m-%dT%H:%M:%S.%f%z"


def _parse_iso(iso_str: str) -> datetime:
    """Fazer parse de string ISO-8601 para datetime (timezone-aware).

    Args:
        iso_str: Timestamp ISO-8601 (ex.: ``"2026-08-02T15:30:00.123456+00:00"``).

    Returns:
        :class:`datetime.datetime` timezone-aware.

    Raises:
        ValueError: Se o formato for invalido.
    """
    # Suporta tanto +00:00 quanto Z
    cleaned = iso_str.replace("Z", "+00:00")
    return datetime.strptime(cleaned, _ISO_FORMAT)


def is_within_window(
    last_seen_at: str, window_seconds: int, reference_time: str | None = None
) -> bool:
    """Verificar se um timestamp esta dentro da janela temporal.

    Args:
        last_seen_at: Timestamp ISO-8601 da ultima ocorrencia.
        window_seconds: Janela em segundos.
        reference_time: Timestamp de referencia (``None`` = agora).

    Returns:
        ``True`` se ``(now - last_seen) <= window_seconds``.
    """
    try:
        last = _parse_iso(last_seen_at)
        ref_str = reference_time or now_iso()
        ref = _parse_iso(ref_str)
        delta = ref - last
        return delta.total_seconds() <= window_seconds
    except (ValueError, TypeError):
        # Se nao conseguir fazer parse, assume fora da janela (seguro)
        return False


@dataclass
class DedupResult:
    """Resultado de uma tentativa de deduplicacao.

    Attributes:
        merged: ``True`` se o evento foi deduplicado no alerta existente.
        record: Alerta resultante (existente atualizado, ou novo).
        updated: ``True`` se o cache foi modificado (para persistencia).
    """

    merged: bool
    record: AlertRecord | None
    updated: bool = False


class DedupCache:
    """Cache thread-safe de fingerprints ativos para deduplicacao.

    Mantem um dict de ``fingerprint -> AlertRecord`` para o conjunto de
    alertas dentro da janela temporal. Usa ``threading.RLock`` para
    acesso concorrente (compativel com o servidor multithread existente
    em ``app/ui/server.py``).

    O cache e populado pelo :class:`~app.services.alert_service.AlertService`
    na inicializacao (consulta SQLite) e mantido em sincronia com as
    operacoes de ciclo de vida do service.
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._entries: dict[str, AlertRecord] = {}

    def lookup(self, fingerprint: str) -> AlertRecord | None:
        """Consultar alerta ativo por fingerprint.

        Args:
            fingerprint: Hash SHA-256 do evento.

        Returns:
            :class:`AlertRecord` se existir em cache, ``None`` caso contrario.
        """
        with self._lock:
            return self._entries.get(fingerprint)

    def remember(self, record: AlertRecord) -> None:
        """Registrar alerta no cache (apos criacao/persistencia).

        Args:
            record: Alerta a manter em cache.
        """
        with self._lock:
            self._entries[record.fingerprint] = record

    def forget(self, fingerprint: str) -> None:
        """Remover alerta do cache (ex.: quando resolvido/expirou).

        Args:
            fingerprint: Fingerprint a remover.
        """
        with self._lock:
            self._entries.pop(fingerprint, None)

    def increment(self, record: AlertRecord) -> None:
        """Incrementar contador e atualizar ``last_seen_at`` in-place.

        Args:
            record: Alerta existente no cache a ser atualizado.
        """
        with self._lock:
            record.count += 1
            record.last_seen_at = now_iso()

    def update(self, record: AlertRecord) -> None:
        """Atualizar entrada no cache (apos alteracao de estado).

        Args:
            record: Alerta com dados atualizados.
        """
        with self._lock:
            self._entries[record.fingerprint] = record

    def clear(self) -> None:
        """Limpar todo o cache (reset)."""
        with self._lock:
            self._entries.clear()

    def __len__(self) -> int:
        with self._lock:
            return len(self._entries)

    def __contains__(self, fingerprint: str) -> bool:
        with self._lock:
            return fingerprint in self._entries

    def items(self) -> list[tuple[str, AlertRecord]]:
        """Retornar snapshot dos items (para iteracao segura)."""
        with self._lock:
            return list(self._entries.items())


def try_dedup(
    cache: DedupCache,
    fingerprint: str,
    window_seconds: int = 300,
) -> DedupResult:
    """Tentar deduplicar um evento contra o cache ativo.

    Se existir um alerta com o mesmo fingerprint e estiver dentro da
    janela temporal, incrementa o contador e retorna o alerta atualizado.
    Caso contrario, retorna ``merged=False``.

    Args:
        cache: Instancia do cache de dedup.
        fingerprint: Fingerprint do evento a deduplicar.
        window_seconds: Janela temporal em segundos (default 5 min).

    Returns:
        :class:`DedupResult` com o resultado da operacao.
    """
    existing = cache.lookup(fingerprint)
    if existing is None:
        return DedupResult(merged=False, record=None, updated=False)

    if not is_within_window(existing.last_seen_at, window_seconds):
        return DedupResult(merged=False, record=None, updated=False)

    cache.increment(existing)
    return DedupResult(merged=True, record=existing, updated=True)
