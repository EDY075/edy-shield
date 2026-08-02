"""Checksum Files — criação e verificação de arquivos de checksum.

Reutiliza o Batch Hashing (:mod:`app.core.algorithms.batch`) e o Hash Checker
(:mod:`app.core.algorithms.hash_checker`) como motores de cálculo — nunca
duplica lógica de hash.

Formatos suportados (extensões): ``.sha256``, ``.sha256sum``, ``.sha1``,
``.md5`` e ``.md5sum``. O parser aceita o formato BSD e GNU:

    <digest>  <filename>       # BSD (2+ espaços)
    <digest> *<filename>       # GNU binary marker

Segurança (ADR-001, ARES-QA-001):
    - Core 100% stdlib — zero dependências externas.
    - Fronteira de paths reutilizada (``resolve_safe_path``): evita path
      traversal nos filenames lidos do arquivo de checksum.
    - ``allowed_root`` respeitado; por padrão é o diretório do próprio
      arquivo de checksum.
    - Digest é a fonte de verdade; comparação via ``safe_compare``
      (tempo constante, ARES-QA-003).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from app.core.algorithms.batch import hash_directory
from app.core.algorithms.hash_checker import compute_file
from app.core.crypto.hashing import HashAlgorithm, normalize_algorithm, safe_compare
from app.core.filesystem.safe_path import resolve_safe_path

#: Extensões reconhecidas de arquivos de checksum.
SUPPORTED_SUFFIXES: frozenset[str] = frozenset(
    {".sha256", ".sha256sum", ".sha1", ".md5", ".md5sum"}
)

#: Tamanho de digest hexadecimal por algoritmo (SHA256=64, SHA1=40, MD5=32).
_DIGEST_LENGTH_BY_NAME: dict[str, int] = {
    "SHA256": 64,
    "SHA1": 40,
    "MD5": 32,
}

#: Expressão regular de um digest hexadecimal (case-insensitive).
_HEX_DIGEST_RE = re.compile(r"^[0-9a-fA-F]+$")


class ChecksumError(ValueError):
    """Erro de domínio ao processar arquivos de checksum."""


@dataclass(frozen=True, slots=True)
class ChecksumEntry:
    """Entrada individual da verificação de checksum.

    Attributes:
        digest: Digest esperado (lido do arquivo de checksum).
        filename: Caminho relativo do arquivo verificado.
        status: ``"ok"`` | ``"mismatch"`` | ``"missing"`` | ``"invalid"``.
        actual: Digest calculado (``None`` se não foi possível).
        error: Mensagem de erro (``None`` quando ok).
    """

    digest: str
    filename: str
    status: str
    actual: str | None = None
    error: str | None = None


@dataclass(frozen=True, slots=True)
class ChecksumReport:
    """Resultado consolidado da verificação de um arquivo de checksum."""

    entries: tuple[ChecksumEntry, ...]
    algorithm: str | None

    @property
    def total(self) -> int:
        return len(self.entries)

    @property
    def ok(self) -> int:
        return sum(1 for e in self.entries if e.status == "ok")

    @property
    def mismatch(self) -> int:
        return sum(1 for e in self.entries if e.status == "mismatch")

    @property
    def missing(self) -> int:
        return sum(1 for e in self.entries if e.status == "missing")

    @property
    def invalid(self) -> int:
        return sum(1 for e in self.entries if e.status == "invalid")

    @property
    def ok_all(self) -> bool:
        """``True`` quando não há mismatch, missing ou invalid."""
        return self.mismatch == 0 and self.missing == 0 and self.invalid == 0


def _detect_algorithm(digest: str) -> str | None:
    """Detectar algoritmo pelo comprimento do digest hexadecimal.

    Args:
        digest: Digest hexadecimal.

    Returns:
        Nome do algoritmo (``"SHA256"``/``"SHA1"``/``"MD5"``) ou ``None``
        quando o comprimento não corresponde a nenhum suportado.
    """
    for name, length in _DIGEST_LENGTH_BY_NAME.items():
        if len(digest) == length:
            return name
    return None


def _parse_line(line: str) -> tuple[str, str] | None:
    """Parse de uma linha de checksum (BSD ou GNU).

    Args:
        line: Linha crua do arquivo (sem quebra final).

    Returns:
        ``(digest, filename)`` para linhas válidas; ``None`` para linhas
        vazias ou comentários (``#``).

    Raises:
        ChecksumError: Para linhas malformadas (sem digest/filename, digest
            não-hexadecimal ou tamanho desconhecido).
    """
    stripped = line.strip()
    if not stripped or stripped.startswith("#"):
        return None

    # Formato BSD: "digest  filename" | GNU: "digest *filename"
    parts = stripped.split(None, 1)
    if len(parts) != 2:
        raise ChecksumError(f"Linha malformada: {line!r}")

    digest, filename = parts[0], parts[1]
    if filename.startswith("*"):
        filename = filename[1:]

    if not _HEX_DIGEST_RE.fullmatch(digest):
        raise ChecksumError(f"Digest não-hexadecimal: {digest!r}")
    if _detect_algorithm(digest) is None:
        raise ChecksumError(f"Comprimento de digest desconhecido ({len(digest)} hex): {digest!r}")
    if not filename:
        raise ChecksumError(f"Filename vazio na linha: {line!r}")

    return digest, filename


def parse_checksum_file(path: Path | str) -> tuple[tuple[str, str], ...]:
    """Ler e validar um arquivo de checksum.

    Linhas vazias e comentários (``#``) são ignorados. Linhas malformadas
    levantam :class:`ChecksumError` com o número da linha.

    Args:
        path: Caminho do arquivo de checksum.

    Returns:
        Tupla de pares ``(digest, filename)`` válidos, na ordem do arquivo.

    Raises:
        ChecksumError: Se alguma linha estiver malformada.
        FileNotFoundError: Se o arquivo não existir.
    """
    target = Path(path)
    entries: list[tuple[str, str]] = []
    with target.open("r", encoding="utf-8", errors="strict") as handle:
        for line_no, line in enumerate(handle, start=1):
            try:
                parsed = _parse_line(line)
            except ChecksumError as exc:
                raise ChecksumError(f"{target.name}:{line_no}: {exc}") from exc
            if parsed is not None:
                entries.append(parsed)
    return tuple(entries)


def _checksum_base_dir(checksum_path: Path) -> Path:
    """Diretório base para resolver filenames (pai do arquivo de checksum)."""
    return checksum_path.resolve().parent


def create_checksum_file(
    directory: Path | str,
    output: Path | str,
    *,
    algorithm: HashAlgorithm | str = "SHA256",
    recursive: bool = False,
    allowed_root: Path | None = None,
) -> int:
    """Criar um arquivo de checksum a partir de um diretório.

    Reutiliza :func:`app.core.algorithms.batch.hash_directory` — nenhuma
    lógica de hash é duplicada.

    Args:
        directory: Diretório a varrer.
        output: Caminho do arquivo de checksum a criar.
        algorithm: Algoritmo (SHA256/SHA1/MD5).
        recursive: Se ``True``, inclui subdiretórios.
        allowed_root: Raiz permitida (padrão: diretório alvo).

    Returns:
        Número de entradas gravadas.

    Raises:
        UnsupportedAlgorithmError: Se o algoritmo for inválido.
    """
    member = normalize_algorithm(algorithm)
    root = Path(directory).resolve()
    out_path = Path(output).resolve()

    # Respeitar allowed_root (quando informado): o diretório alvo deve estar
    # dentro da raiz permitida.
    if allowed_root is not None:
        allowed = Path(allowed_root).resolve()
        try:
            root.relative_to(allowed)
        except ValueError as exc:
            raise ChecksumError(f"Diretório alvo fora da raiz permitida: {root}") from exc

    results = hash_directory(root, member, recursive=recursive)

    lines: list[str] = []
    for entry, err in results:
        if err is not None or entry is None or entry.path is None:
            continue
        rel = entry.path
        # Nunca incluir arquivos de checksum na própria varredura (evita
        # auto-referência e incluir checksums já existentes no diretório).
        if rel.suffix.lower() in SUPPORTED_SUFFIXES:
            continue
        if (root / rel).resolve() == out_path:
            continue
        lines.append(f"{entry.hexdigest}  {rel.as_posix()}")

    lines.sort()
    with out_path.open("w", encoding="utf-8") as handle:
        handle.write("\n".join(lines))
        if lines:
            handle.write("\n")

    return len(lines)


def verify_checksum_file(
    checksum_path: Path | str,
    *,
    allowed_root: Path | None = None,
    chunk_size: int = 65536,
) -> ChecksumReport:
    """Verificar um arquivo de checksum contra os arquivos referenciados.

    Para cada entrada válida do arquivo, o digest é recalculado com
    :func:`app.core.algorithms.hash_checker.compute_file` e comparado em
    tempo constante (``safe_compare``).

    A segurança do filename é garantida por ``resolve_safe_path`` com a raiz
    derivada (diretório do arquivo de checksum, salvo ``allowed_root``
    explícito) — filenames fora da raiz viram entrada ``invalid``.

    Args:
        checksum_path: Caminho do arquivo de checksum.
        allowed_root: Raiz permitida (padrão: diretório do arquivo).
        chunk_size: Bloco de leitura.

    Returns:
        :class:`ChecksumReport` consolidado.

    Raises:
        FileNotFoundError: Se o arquivo de checksum não existir.
    """
    target = Path(checksum_path).resolve()
    base = _checksum_base_dir(target)
    effective_root = allowed_root if allowed_root is not None else base

    entries: list[ChecksumEntry] = []
    with target.open("r", encoding="utf-8", errors="strict") as handle:
        for line_no, line in enumerate(handle, start=1):
            try:
                parsed = _parse_line(line)
            except ChecksumError as exc:
                entries.append(
                    ChecksumEntry(
                        digest="",
                        filename="",
                        status="invalid",
                        error=f"{target.name}:{line_no}: {exc}",
                    )
                )
                continue
            if parsed is None:
                continue

            digest, filename = parsed
            file_path = base / filename
            try:
                resolved = resolve_safe_path(file_path, allowed_root=effective_root, strict=True)
            except FileNotFoundError:
                entries.append(ChecksumEntry(digest=digest, filename=filename, status="missing"))
                continue
            except Exception as exc:
                entries.append(
                    ChecksumEntry(
                        digest=digest,
                        filename=filename,
                        status="invalid",
                        error=str(exc),
                    )
                )
                continue

            algorithm = _detect_algorithm(digest)
            if algorithm is None:
                entries.append(
                    ChecksumEntry(
                        digest=digest,
                        filename=filename,
                        status="invalid",
                        error="comprimento de digest desconhecido",
                    )
                )
                continue

            if not resolved.is_file():
                entries.append(ChecksumEntry(digest=digest, filename=filename, status="missing"))
                continue

            try:
                actual = compute_file(
                    resolved, algorithm, chunk_size=chunk_size, allowed_root=effective_root
                )
            except Exception as exc:
                entries.append(
                    ChecksumEntry(
                        digest=digest,
                        filename=filename,
                        status="invalid",
                        error=str(exc),
                    )
                )
                continue

            if safe_compare(actual, digest.lower()):
                entries.append(
                    ChecksumEntry(digest=digest, filename=filename, status="ok", actual=actual)
                )
            else:
                entries.append(
                    ChecksumEntry(
                        digest=digest,
                        filename=filename,
                        status="mismatch",
                        actual=actual,
                    )
                )

    return ChecksumReport(entries=tuple(entries), algorithm=None)
