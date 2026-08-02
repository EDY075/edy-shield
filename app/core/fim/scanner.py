"""Scanner do File Integrity Monitor (Sprint 5 — FIM v2.0).

Responsável por:

* :func:`scan_snapshot` — varrer um alvo (diretório ou arquivo) e produzir
  um :class:`Snapshot` com as entradas de integridade.
* :func:`compare_baseline_snapshot` — comparar uma baseline contra uma
  snapshot e produzir um :class:`FimDiff`.
* :func:`_walk_target` — iterar arquivos regulares em ordem determinística.

Regras de arquitetura (ADR-FIM-002/003/005):

* O **digest criptográfico** é a fonte de verdade; ``mtime``/``size`` são
  triagem/diagnóstico (ADR-FIM-002).
* **Não segue symlinks** (ADR-FIM-003) — são registrados como ``ignored``
  para não permitir fuga da raiz nem leitura de alvos arbitrários.
* Reutiliza :func:`compute_file` (com ``O_NOFOLLOW`` + ``fstat``, mitigação
  TOCTOU ARES-QA-008) e a fronteira de paths (:func:`resolve_safe_path`) —
  o scanner nunca lê o filesystem por fora do Core (ADR-FIM-005).
* Varredura sob demanda (ADR-FIM-004) — nada de watchdog/agendador.
"""

from __future__ import annotations

import os
import posixpath
import stat
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path

from app.core.algorithms import compute_file
from app.core.crypto import HashAlgorithm, normalize_algorithm
from app.core.exceptions import FimError
from app.core.filesystem.safe_path import resolve_safe_path, validate_allowed_root
from app.core.fim.models import Baseline, BaselineEntry, FimDiff, Snapshot
from app.core.validators import validate_chunk_size

#: Tamanho padrão de bloco de leitura (64 KiB — mesmo do Hash Checker).
DEFAULT_CHUNK_SIZE: int = 65536


def _mtime_iso(st_mtime: float) -> str:
    """Formatar um timestamp POSIX como ISO 8601 UTC determinístico."""
    return datetime.fromtimestamp(st_mtime, tz=UTC).astimezone(UTC).isoformat()


def _permissions_octal(st_mode: int) -> str:
    """Extrair o modo de permissões (ex.: ``644``) de um ``st_mode``.

    Quando o filesystem não expõe permissões (ex.: 0), retorna ``"0"`` —
    o chamador pode tratar como indisponível.
    """
    return f"{stat.S_IMODE(st_mode):o}"


def _entry_from_path(
    file_path: Path,
    *,
    root: Path,
    algorithm: HashAlgorithm,
    rel_path: str,
    chunk_size: int,
) -> BaselineEntry | None:
    """Criar a entrada de integridade de um arquivo regular.

    Reutiliza :func:`compute_file` (que re-valida a fronteira com
    ``O_NOFOLLOW`` + ``fstat``) e captura metadados via ``os.stat``.

    Args:
        file_path: Caminho absoluto do arquivo.
        root: Raiz permitida (contém o arquivo).
        algorithm: Algoritmo normalizado.
        rel_path: Caminho relativo POSIX (ex.: ``sub/a.txt``).
        chunk_size: Bytes lidos por iteração.

    Returns:
        :class:`BaselineEntry` ou ``None`` quando o arquivo não é regular
        (ex.: symlink) — o chamador registra como ignorado.
    """
    try:
        digest = compute_file(file_path, algorithm, chunk_size=chunk_size, allowed_root=root)
        st = os.stat(file_path, follow_symlinks=False)
    except OSError:
        return None
    if not stat.S_ISREG(st.st_mode):
        return None
    return BaselineEntry(
        path=rel_path,
        hexdigest=digest.lower(),
        size_bytes=st.st_size,
        mtime_iso=_mtime_iso(st.st_mtime),
        permissions=_permissions_octal(st.st_mode),
    )


def _walk_target(
    target: Path,
    *,
    recursive: bool,
    follow_symlinks: bool,
) -> tuple[list[tuple[str, Path]], list[str]]:
    """Iterar arquivos regulares em ordem determinística (os.scandir).

    Retorna ``(files, ignored)``:

    * ``files`` — lista de ``(rel_path_posix, absolute_path)`` ordenada por
      ``rel_path_posix`` (determinística).
    * ``ignored`` — paths relativos ignorados (symlinks, quando
      ``follow_symlinks=False``, e arquivos inacessíveis).

    Não segue symlinks (ADR-FIM-003) e não desce em diretórios inacessíveis
    sem abortar a varredura (observados como ignorados).
    """
    files: list[tuple[str, Path]] = []
    ignored: list[str] = []

    def visit(directory: Path, rel_prefix: str) -> None:
        try:
            entries = list(os.scandir(directory))
        except OSError:
            return
        for entry in sorted(entries, key=lambda item: item.name):
            rel = posixpath.join(rel_prefix, entry.name)
            full = Path(entry.path)
            if entry.is_symlink() and not follow_symlinks:
                ignored.append(rel)
                continue
            try:
                is_dir = entry.is_dir(follow_symlinks=follow_symlinks)
                is_file = entry.is_file(follow_symlinks=follow_symlinks)
            except OSError:
                ignored.append(rel)
                continue
            if is_dir:
                if recursive:
                    visit(full, rel)
                continue
            if is_file:
                files.append((rel, full))

    if target.is_file():
        files.append((target.name, target))
    else:
        visit(target, "")

    files.sort(key=lambda item: item[0])
    ignored.sort()
    return files, ignored


def scan_snapshot(
    target: Path | str,
    *,
    algorithm: HashAlgorithm | str = HashAlgorithm.SHA256,
    recursive: bool = True,
    allowed_root: Path | None = None,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    follow_symlinks: bool = False,
    now: datetime | None = None,
) -> Snapshot:
    """Varrer um alvo e gerar um :class:`Snapshot` de integridade.

    Args:
        target: Diretório (ou arquivo) a fotografar.
        algorithm: Algoritmo de hash (whitelist do Core).
        recursive: Quando ``True``, desce recursivamente em subdiretórios.
        allowed_root: Raiz permitida; ``None`` deriva do alvo (ARES-QA-028).
        chunk_size: Bytes lidos por iteração (positivo).
        follow_symlinks: Sempre ``False`` por padrão (ADR-FIM-003).
        now: Momento UTC injetável (testes).

    Returns:
        Snapshot com entradas ordenadas e paths relativos POSIX.

    Raises:
        FimError: Se o alvo escapa da raiz ou é inválido.
        FileNotFoundError: Se o alvo não existe.
        ValueError: Se ``chunk_size`` não for positivo.
        UnsupportedAlgorithmError: Se o algoritmo não for suportado.
    """
    member = normalize_algorithm(algorithm)
    validate_chunk_size(chunk_size)

    resolved_target = Path(target).resolve()
    if not resolved_target.exists():
        raise FileNotFoundError(f"Target não encontrado: {resolved_target.name}")

    if allowed_root is not None:
        root = validate_allowed_root(allowed_root)
    elif resolved_target.is_dir():
        root = resolved_target
    else:
        root = resolved_target.parent

    # Fronteira de paths: o alvo deve estar contido na raiz efetiva.
    if not resolved_target.is_dir():
        resolve_safe_path(resolved_target, allowed_root=root, strict=True)

    files, ignored = _walk_target(
        resolved_target,
        recursive=recursive,
        follow_symlinks=follow_symlinks,
    )

    entries: list[BaselineEntry] = []
    for rel, full in files:
        try:
            entry = _entry_from_path(
                full,
                root=root,
                algorithm=member,
                rel_path=rel,
                chunk_size=chunk_size,
            )
        except FimError:
            ignored.append(rel)
            continue
        if entry is not None:
            entries.append(entry)
        else:
            ignored.append(rel)

    entries.sort(key=lambda entry: entry.path)
    return Snapshot(
        root=str(resolved_target),
        algorithm=member.name,
        created_at=(now or datetime.now(UTC)).astimezone(UTC).isoformat(),
        entries=tuple(entries),
        ignored=tuple(sorted(set(ignored))),
    )


def compare_baseline_snapshot(baseline: Baseline, snapshot: Snapshot) -> FimDiff:
    """Comparar uma baseline contra uma snapshot e produzir um diff.

    A **fonte de verdade é o digest** (ADR-FIM-002): dois arquivos são
    iguais quando ``hexdigest`` casa; caso contrário, o arquivo é
    ``modified`` (independentemente de ``mtime``/``size``).

    Args:
        baseline: Baseline de referência.
        snapshot: Snapshot atual do alvo.

    Returns:
        :class:`FimDiff` com added/modified/removed/unchanged/ignored.

    Raises:
        FimError: Se ``algorithm`` ou ``root`` divergirem da baseline.
    """
    if baseline.algorithm.upper() != snapshot.algorithm.upper():
        raise FimError(
            f"Algoritmo da baseline ({baseline.algorithm}) difere da "
            f"varredura ({snapshot.algorithm})."
        )
    baseline_root = Path(baseline.root).resolve()
    snapshot_root = Path(snapshot.root).resolve()
    if baseline_root != snapshot_root:
        raise FimError(
            f"Raiz da baseline ({baseline.root}) difere do alvo varrido ({snapshot.root})."
        )

    baseline_map = {entry.path: entry for entry in baseline.entries}
    snapshot_map = {entry.path: entry for entry in snapshot.entries}

    added: list[str] = []
    modified: list[str] = []
    removed: list[str] = []
    unchanged: list[str] = []

    for path in sorted(snapshot_map):
        if path not in baseline_map:
            added.append(path)
            continue
        if snapshot_map[path].hexdigest.lower() != baseline_map[path].hexdigest.lower():
            modified.append(path)
        else:
            unchanged.append(path)

    for path in sorted(baseline_map):
        if path not in snapshot_map:
            removed.append(path)

    return FimDiff(
        baseline_id=baseline.baseline_id,
        algorithm=baseline.algorithm,
        scanned_at=(datetime.now(UTC)).astimezone(UTC).isoformat(),
        added=tuple(added),
        modified=tuple(modified),
        removed=tuple(removed),
        unchanged=tuple(unchanged),
        ignored=tuple(sorted(set(snapshot.ignored))),
    )


def _unique_sorted(values: Iterable[str]) -> tuple[str, ...]:
    """Ordenar e deduplicar uma coleção de paths (helper de diff)."""
    return tuple(sorted(set(values)))
