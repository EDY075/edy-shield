"""Criação e carga de baselines do File Integrity Monitor (Sprint 5).

APIs públicas do FIM para baseline:

* :func:`create_baseline` — fotografia criptográfica de um diretório/arquivo.
* :func:`save_baseline` — persistir uma baseline como JSON determinístico.
* :func:`load_baseline` — carregar/validar um arquivo JSON (round-trip).

A baseline é um :class:`~app.core.fim.models.Baseline`: metadados +
entradas de integridade (``path`` relativo POSIX, ``hexdigest`` — fonte de
verdade, ``size_bytes``, ``mtime_iso`` e ``permissions`` quando possível).

Regras (ADR-FIM-001/002):

* JSON **determinístico** — mesmas entradas geram o mesmo arquivo byte a
  byte (ordenado por ``path``, chaves em ordem canônica).
* **Round-trip validado** na leitura — baseline corrompida é rejeitada com
  :class:`~app.core.exceptions.BaselineCorruptionError`, nunca retornada
  parcialmente (RF-04).
"""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from pathlib import Path

from app.core.crypto import HashAlgorithm, normalize_algorithm
from app.core.exceptions import BaselineCorruptionError
from app.core.fim.ids import build_baseline_id
from app.core.fim.models import Baseline, BaselineEntry
from app.core.fim.scanner import DEFAULT_CHUNK_SIZE, scan_snapshot
from app.core.validators import validate_chunk_size

#: Charset seguro para baseline_id (padrão HistoryStore) — anti path traversal.
_SAFE_ID_RE = re.compile(r"[^A-Za-z0-9_.-]")
#: Formato canônico do baseline_id: fim_<algo>_<UTC %Y%m%dT%H%M%SZ>.
#: Fração de microsegundos opcional (``Z<digits>``) — usada para garantir
#: unicidade quando duas baselines são criadas no mesmo segundo (ARES-QA-033).
_BASELINE_ID_RE = re.compile(r"^fim_[a-z0-9]+_\d{8}T\d{6}Z\d*$")
#: Versão atual do formato de baseline.
BASELINE_VERSION = 1

#: Tamanho esperado do digest hex por algoritmo (usado na validação).
_DIGEST_LENGTHS: dict[str, int] = {
    "SHA256": 64,
    "SHA1": 40,
    "MD5": 32,
}


def _validate_baseline_id(value: str) -> str:
    """Validar o formato e o charset seguro do baseline_id.

    Raises:
        BaselineCorruptionError: Se o formato não casar com a spec.
    """
    if not _BASELINE_ID_RE.match(value):
        raise BaselineCorruptionError(f"baseline_id inválido: {value!r}")
    if _SAFE_ID_RE.search(value):
        raise BaselineCorruptionError(f"baseline_id com charset inseguro: {value!r}")
    return value


def _validate_entry(entry: BaselineEntry, algorithm: str) -> None:
    """Validar uma entrada carregada (regras de round-trip, seção 6.2).

    Raises:
        BaselineCorruptionError: Se a entrada violar as regras.
    """
    path = entry.path
    # Rejeita paths absolutos em qualquer plataforma: POSIX ("/..."), Windows
    # ("C:\\...") e prefixo de drive ("C:/...") mesmo no Linux (compat
    # multiplataforma — Path.is_absolute() não detecta "C:/x" no POSIX).
    absolute = (
        Path(path).is_absolute()
        or path.startswith("/")
        or path.startswith("\\")
        or bool(re.match(r"^[A-Za-z]:[\\/]", path))
    )
    if not path or absolute:
        raise BaselineCorruptionError(f"path deve ser relativo: {path!r}")
    if ".." in Path(path).parts:
        raise BaselineCorruptionError(f"path não pode conter '..': {path!r}")

    expected = _DIGEST_LENGTHS.get(algorithm.upper())
    if expected is not None and len(entry.hexdigest) != expected:
        raise BaselineCorruptionError(
            f"hexdigest de {entry.path} deve ter {expected} chars "
            f"para {algorithm}, got {len(entry.hexdigest)}."
        )
    if not re.fullmatch(r"[0-9a-f]+", entry.hexdigest.lower()):
        raise BaselineCorruptionError(f"hexdigest de {entry.path} não é hexadecimal válido.")
    if entry.size_bytes < 0:
        raise BaselineCorruptionError(f"size_bytes negativo em {entry.path}.")
    try:
        datetime.fromisoformat(entry.mtime_iso)
    except ValueError as exc:
        raise BaselineCorruptionError(
            f"mtime_iso inválido em {entry.path}: {entry.mtime_iso!r}."
        ) from exc


def _round_trip_validate(baseline: Baseline) -> None:
    """Validar uma baseline completa (regras de round-trip, seção 6.2).

    Raises:
        BaselineCorruptionError: Se qualquer regra for violada.
    """
    if baseline.version != BASELINE_VERSION:
        raise BaselineCorruptionError(f"versão de baseline não suportada: {baseline.version}.")
    _validate_baseline_id(baseline.baseline_id)
    normalize_algorithm(baseline.algorithm)  # whitelist do Core

    seen: set[str] = set()
    for entry in baseline.entries:
        if entry.path in seen:
            raise BaselineCorruptionError(f"path duplicado na baseline: {entry.path!r}")
        seen.add(entry.path)
        _validate_entry(entry, baseline.algorithm)


def create_baseline(
    target: Path | str,
    *,
    algorithm: HashAlgorithm | str = HashAlgorithm.SHA256,
    recursive: bool = True,
    allowed_root: Path | None = None,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    follow_symlinks: bool = False,
    now: datetime | None = None,
) -> Baseline:
    """Criar uma baseline de integridade de um diretório ou arquivo.

    Compõe :func:`scan_snapshot` (varredura + digests) com os metadados da
    baseline: ``baseline_id`` (formato canônico), ``version``, ``created_at``
    e ``root`` (alvo resolvido).

    Args:
        target: Diretório ou arquivo a fotografar.
        algorithm: Algoritmo de hash (padrão SHA-256).
        recursive: Varre recursivamente subdiretórios (padrão ``True``).
        allowed_root: Raiz permitida; ``None`` deriva do alvo (ARES-QA-028).
        chunk_size: Bytes lidos por iteração.
        follow_symlinks: Sempre ``False`` (ADR-FIM-003).
        now: Momento UTC injetável (testes).

    Returns:
        :class:`Baseline` com entradas ordenadas.

    Raises:
        FileNotFoundError: Se o alvo não existir.
        UnsupportedAlgorithmError: Se o algoritmo for inválido.
        ValueError: Se ``chunk_size`` não for positivo.
        HashError: Se o alvo escapar da raiz.
    """
    member = normalize_algorithm(algorithm)
    validate_chunk_size(chunk_size)

    snapshot = scan_snapshot(
        target,
        algorithm=member,
        recursive=recursive,
        allowed_root=allowed_root,
        chunk_size=chunk_size,
        follow_symlinks=follow_symlinks,
        now=now,
    )

    created = (now or datetime.now(UTC)).astimezone(UTC).isoformat()
    baseline = Baseline(
        baseline_id=build_baseline_id(member.name, now),
        algorithm=member.name,
        version=BASELINE_VERSION,
        created_at=created,
        root=snapshot.root,
        entries=snapshot.entries,
    )
    _round_trip_validate(baseline)
    return baseline


def save_baseline(baseline: Baseline, path: Path | str) -> Path:
    """Persistir uma baseline como JSON determinístico.

    Determinístico: entradas já ordenadas por ``path`` e chaves do
    ``to_dict`` em ordem canônica (sem ``sort_keys``), ``ensure_ascii=False``.

    Args:
        baseline: Baseline a persistir.
        path: Caminho de destino (ex.: ``baseline.json``).

    Returns:
        O caminho resolvido do arquivo gravado.
    """
    _round_trip_validate(baseline)
    target = Path(path).resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(baseline.to_dict(), indent=2, ensure_ascii=False)
    target.write_text(payload + "\n", encoding="utf-8")
    return target


def load_baseline(path: Path | str) -> Baseline:
    """Carregar e validar um arquivo de baseline JSON (round-trip).

    Args:
        path: Caminho do arquivo JSON.

    Returns:
        :class:`Baseline` validada.

    Raises:
        FileNotFoundError: Se o arquivo não existir.
        BaselineCorruptionError: Se o JSON for malformado, campos ausentes,
            tipos errados ou regras de round-trip violadas.
    """
    source = Path(path)
    try:
        raw = source.read_text(encoding="utf-8")
    except OSError as exc:
        raise FileNotFoundError(f"Arquivo de baseline não encontrado: {source.name}") from exc

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise BaselineCorruptionError(f"JSON malformado: {exc}") from exc
    if not isinstance(data, dict):
        raise BaselineCorruptionError("baseline deve ser um objeto JSON.")

    try:
        baseline = Baseline.from_dict(data)
    except (KeyError, TypeError, ValueError) as exc:
        raise BaselineCorruptionError(f"baseline inválida: {exc}") from exc

    _round_trip_validate(baseline)
    return baseline
