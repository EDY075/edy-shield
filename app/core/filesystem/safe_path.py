"""Operações seguras de filesystem do núcleo EDY Shield (Missão 2).

Fronteira única de validação de caminhos do Core: contenção na raiz
permitida, rejeição de ``..``/symlinks que escapam e de arquivos especiais
(FIFO, devices, sockets). Migra a lógica que residia em
:mod:`app.services.file_utils` para o Core (ARES-QA-001, ARES-QA-005,
ARES-QA-007).

Regras aplicadas em todas as funções:

    * Os caminhos são **resolvidos** (absolutos, incluindo symlinks) antes
      de qualquer validação — ``Path.resolve()`` por design.
    * A fuga da raiz é detectada com ``Path.relative_to`` (try/except
      ``ValueError``).
    * Mensagens de erro nunca expõem caminhos absolutos — usam
      ``target.name`` (ARES-QA-005).

Dependências: importa apenas o Core (exceções de domínio). Não importa
``app.services`` nem ``app.core.algorithms`` (evita ciclos de imports).
"""

from pathlib import Path

from app.core.exceptions import HashError


def validate_allowed_root(root: Path | None) -> Path:
    """Validate and resolve the allowed root directory.

    Args:
        root: Directory to validate. When ``None``, the current working
            directory is used.

    Returns:
        The resolved absolute root directory.

    Raises:
        TypeError: If ``root`` is neither a ``Path`` nor ``None``.
        NotADirectoryError: If ``root`` exists but is not a directory
            (ARES-QA-020).
        FileNotFoundError: If ``root`` does not exist and is not ``None``.
    """
    if root is not None and not isinstance(root, Path):
        raise TypeError(f"allowed_root must be a Path or None, got {type(root).__name__}.")
    if root is None:
        return Path.cwd().resolve()
    resolved = root.resolve()
    if not resolved.exists():
        raise FileNotFoundError(f"allowed_root does not exist: {_safe_name(root)}")
    if not resolved.is_dir():
        raise NotADirectoryError(f"allowed_root is not a directory: {_safe_name(root)}")
    return resolved


def _safe_name(path: Path) -> str:
    """Return a safe display name for a path (never full absolute path)."""
    return path.name if path.name else str(path)


def is_within_root(resolved: Path, root: Path) -> bool:
    """Return ``True`` when ``resolved`` is inside (or equals) ``root``.

    Uses :meth:`pathlib.Path.relative_to` — a ``ValueError`` means the
    path escaped the root.

    Args:
        resolved: Absolute, already-resolved path to test.
        root: Absolute, already-resolved root directory.

    Returns:
        ``True`` when ``resolved`` is inside ``root``, ``False`` otherwise.
    """
    try:
        resolved.relative_to(root)
    except ValueError:
        return False
    return True


def resolve_safe_path(
    path: Path | str,
    *,
    allowed_root: Path | None = None,
    strict: bool = True,
) -> Path:
    """Resolve and validate that a path stays inside the allowed root.

    This is the **single** source of path validation for the application.
    Resolves the absolute, symlink-free path and rejects any path that
    escapes ``allowed_root`` — ``..`` traversal, absolute paths outside
    the root, or symlinks resolving outside (ARES-QA-001).

    Args:
        path: The candidate path (``Path`` or ``str``, absolute or relative
            to the process cwd).
        allowed_root: Directory that the resolved path must stay inside.
            When ``None``, the current working directory is used.
        strict: When ``True`` (default), raise
            :class:`FileNotFoundError` if the resolved file does not exist.

    Returns:
        The resolved absolute path, guaranteed to be inside ``allowed_root``.

    Raises:
        HashError: If the path escapes the allowed root.
        FileNotFoundError: If ``strict`` is ``True`` and the file does not
            exist.
    """
    root = validate_allowed_root(allowed_root)
    resolved = Path(path).resolve()

    if not is_within_root(resolved, root):
        raise HashError("acesso negado: caminho fora do diretório permitido")

    if strict and not resolved.exists():
        raise FileNotFoundError(f"File not found: {resolved.name}")

    return resolved


def ensure_regular_file(target: Path) -> None:
    """Reject directories and non-regular (special) files.

    Mitiga DoS por arquivos especiais (FIFO, devices, sockets) que
    poderiam travar o processo em um ``open`` de leitura (ARES-QA-007).

    Args:
        target: Already-resolved path to validate.

    Raises:
        IsADirectoryError: If ``target`` is a directory.
        HashError: If ``target`` exists but is not a regular file.
    """
    if target.is_dir():
        raise IsADirectoryError(f"Cannot hash a directory: {target.name}")

    if not target.is_file():
        raise HashError(f"Cannot hash non-regular file: {target.name}")
