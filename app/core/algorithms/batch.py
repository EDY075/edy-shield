"""Batch Hashing — cálculo de hashes para múltiplos arquivos e diretórios.

Reutiliza :func:`app.core.algorithms.compute_file` como motor de cálculo,
sem duplicar lógica de hash.

Suporte:
    - Lista de arquivos individuais.
    - Diretório com arquivos no nível superior.
    - Diretório com varredura recursiva (subdiretórios).
    - Ignora automaticamente diretórios durante a varredura.
    - Ordenação determinística dos resultados (por caminho).
    - Tratamento individual de erros — falha em um arquivo não
      interrompe o lote.

Arquitetura (ADR-002, ADR-001):
    - 100% stdlib — zero dependências externas.
    - Usa :func:`app.core.algorithms.compute_file` para cada arquivo.
    - Usa :mod:`pathlib` para varredura e filtragem.
    - Respeita a fronteira de paths do Core via ``allowed_root``.
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from app.core.algorithms.hash_checker import compute_file
from app.core.crypto.hashing import HashAlgorithm, normalize_algorithm
from app.core.models.hashes import HashResult

BatchResult = tuple[HashResult | None, Exception | None]
"""Resultado de um único arquivo no lote.

Sucesso: ``(HashResult, None)``
Erro: ``(None, Exception)``
"""


def hash_files(
    paths: Iterable[Path | str],
    algorithm: HashAlgorithm | str,
    *,
    chunk_size: int = 65536,
    allowed_root: Path | None = None,
) -> list[BatchResult]:
    """Calcular hashes de uma lista explícita de arquivos.

    Cada arquivo é processado com :func:`compute_file`. Erros em um arquivo
    não interrompem os demais.

    Args:
        paths: Caminhos dos arquivos a hashear.
        algorithm: Algoritmo de hash (SHA256, SHA1 ou MD5).
        chunk_size: Tamanho do bloco de leitura (padrão 64 KiB).
        allowed_root: Raiz permitida para validação de paths.

    Returns:
        Lista de tuplas ``(HashResult | None, Exception | None)``,
        ordenada por caminho absoluto.
    """
    # Validar algoritmo imediatamente (antes de qualquer I/O)
    member = normalize_algorithm(algorithm)

    ordered = sorted({Path(p) for p in paths}, key=lambda p: p.resolve())

    results: list[BatchResult] = []
    for path in ordered:
        # Derivar allowed_root do diretório pai do arquivo (ARES-QA-028)
        file_root = allowed_root if allowed_root is not None else path.parent.resolve()
        try:
            digest = compute_file(path, member, chunk_size=chunk_size, allowed_root=file_root)
            entry = HashResult(
                algorithm=member.name,
                hexdigest=digest,
                source="file",
                path=path,
                size_bytes=None,
            )
            results.append((entry, None))
        except Exception as exc:
            results.append((None, exc))

    return results


def hash_directory(
    directory: Path | str,
    algorithm: HashAlgorithm | str,
    *,
    recursive: bool = False,
    chunk_size: int = 65536,
) -> list[BatchResult]:
    """Varrer um diretório e calcular hashes de todos os arquivos regulares.

    Ignora diretórios e arquivos especiais. Ordena deterministicamente por
    caminho. Se ``recursive=True``, desce recursivamente pelos subdiretórios.

    Args:
        directory: Diretório raiz para varredura.
        algorithm: Algoritmo de hash.
        recursive: Se ``True``, varre recursivamente.
        chunk_size: Tamanho do bloco de leitura.

    Returns:
        Lista de ``(HashResult | None, Exception | None)``, ordenada por
        caminho relativo ao diretório raiz.

    Raises:
        FileNotFoundError: Se o diretório não existir.
        NotADirectoryError: Se ``directory`` for um arquivo.
        UnsupportedAlgorithmError: Se o algoritmo for inválido.
    """
    # Validar algoritmo imediatamente
    member = normalize_algorithm(algorithm)

    root = Path(directory).resolve()
    if not root.exists():
        raise FileNotFoundError(f"Diretório não encontrado: {directory}")
    if not root.is_dir():
        raise NotADirectoryError(f"Esperado diretório, mas é arquivo: {directory}")

    pattern = "**/*" if recursive else "*"
    raw_paths = sorted(p for p in root.glob(pattern) if p.is_file())

    results: list[BatchResult] = []
    for file_path in raw_paths:
        rel = file_path.relative_to(root)
        try:
            digest = compute_file(file_path, member, chunk_size=chunk_size, allowed_root=root)
            entry = HashResult(
                algorithm=member.name,
                hexdigest=digest,
                source="file",
                path=rel,
                size_bytes=None,
            )
            results.append((entry, None))
        except Exception as exc:
            results.append((None, exc))

    return results


def _batch_summary(results: list[BatchResult]) -> dict[str, int]:
    """Resumo executivo (interno) de um lote de resultados."""
    total = len(results)
    ok = sum(1 for r, e in results if e is None)
    errs = total - ok
    return {"total": total, "ok": ok, "errors": errs}
