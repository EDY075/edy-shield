"""CLI real do EDY Shield — comandos ``hash`` e ``verify`` (Missão 3).

Interface via ``argparse`` (stdlib, sem dependências externas). O entrypoint
``edyshield`` do ``pyproject.toml`` aponta para :func:`main`, resolvendo o
achado ARES-QA-021.

Comandos:

    edyshield hash <path> [--algorithm SHA256] [--root DIR]
    edyshield verify <path> --expected <HASH> [--algorithm SHA256] [--root DIR]
    edyshield --help
    edyshield --version
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from app import __version__
from app.core.algorithms import compute, verify_file
from app.core.config import Settings, load_settings
from app.core.exceptions import EDYShieldError
from app.core.logging import get_logger, setup_logging

logger = get_logger("cli.hash_cmd")

_ALGORITHM_CHOICES = ["SHA256", "SHA1", "MD5"]


def _build_parser() -> argparse.ArgumentParser:
    """Construir o parser de argumentos da CLI."""
    parser = argparse.ArgumentParser(
        prog="edyshield",
        description=(
            "EDY Shield — plataforma modular de cibersegurança defensiva. "
            "Calcula e verifica hashes de integridade."
        ),
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
        help="mostrar a versão e sair",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    hash_parser = subparsers.add_parser(
        "hash",
        help="calcular o hash de um arquivo ou texto",
        description="Calcula o hash de um arquivo e imprime o hexdigest.",
    )
    hash_parser.add_argument("source", help="caminho do arquivo ou texto")
    hash_parser.add_argument(
        "--algorithm",
        choices=_ALGORITHM_CHOICES,
        default=None,
        help="algoritmo de hash (padrão: configuração ou SHA256)",
    )
    hash_parser.add_argument(
        "--root",
        default=None,
        help="diretório raiz permitido (padrão: diretório de trabalho atual)",
    )

    verify_parser = subparsers.add_parser(
        "verify",
        help="verificar o hash de um arquivo contra um digest esperado",
        description="Compara o hash calculado com o digest esperado.",
    )
    verify_parser.add_argument("source", help="caminho do arquivo")
    verify_parser.add_argument(
        "--expected",
        required=True,
        help="digest hexadecimal esperado",
    )
    verify_parser.add_argument(
        "--algorithm",
        choices=_ALGORITHM_CHOICES,
        default=None,
        help="algoritmo de hash (padrão: configuração ou SHA256)",
    )
    verify_parser.add_argument(
        "--root",
        default=None,
        help="diretório raiz permitido (padrão: diretório de trabalho atual)",
    )

    return parser


EXIT_SUCCESS = 0
EXIT_MISMATCH = 1
EXIT_ERROR = 2


def main(argv: list[str] | None = None) -> int:
    """Ponto de entrada da CLI.

    Args:
        argv: Argumentos da linha de comando (``None`` usa ``sys.argv[1:]``).

    Returns:
        Código de saída:
        - ``0`` sucesso (hash calculado / verificação MATCH)
        - ``1`` verificação MISMATCH (apenas ``verify``)
        - ``2`` erro de domínio / validação / inesperado
        (ARES-QA-029)
    """
    try:
        settings = load_settings()
    except ValueError as exc:
        # Configuração de ambiente inválida não deve gerar traceback cru
        # (ARES-QA-026): mensagem legível + exit code 2.
        print(f"erro: {exc}", file=sys.stderr)
        return EXIT_ERROR
    setup_logging(settings)

    parser = _build_parser()

    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        # --help / --version disparam SystemExit(0) no argparse; expor como
        # código de saída para que main() seja testável e retorne int.
        return int(exc.code or 0)

    algorithm = args.algorithm or settings.default_hash_algorithm
    # Prioridade de raiz permitida (ARES-QA-028): --root explícito > env
    # EDY_ALLOWED_ROOT > diretório pai do arquivo alvo (resolvido).
    if args.root:
        root: Path | None = Path(args.root)
    else:
        root = settings.allowed_root
        if settings.allowed_root is not None:
            logger.warning(
                "EDY_ALLOWED_ROOT está definido (%s); usado como raiz permitida.",
                settings.allowed_root,
            )

    try:
        if args.command == "hash":
            return _cmd_hash(args.source, algorithm, root, settings)
        if args.command == "verify":
            return _cmd_verify(args.source, args.expected, algorithm, root, settings)
    except SystemExit:
        raise
    except EDYShieldError as exc:
        logger.error("%s", exc)
        print(f"erro: {exc}", file=sys.stderr)
        return EXIT_ERROR
    except (FileNotFoundError, IsADirectoryError, ValueError, TypeError) as exc:
        logger.error("%s", exc)
        print(f"erro: {exc}", file=sys.stderr)
        return EXIT_ERROR

    return EXIT_ERROR


def _resolve_root(source: str, root: Path | None) -> Path | None:
    """Derivar a raiz permitida quando o usuário não a informa.

    Quando ``--root`` e ``EDY_ALLOWED_ROOT`` não estão definidos, a raiz é o
    diretório pai do arquivo alvo — permite hashear qualquer caminho absoluto
    mantendo a contenção da fronteira (nada fora desse diretório é permitido).

    Se o source for um arquivo **existente** (mesmo sem extensão), usa o pai
    resolvido (ARES-QA-025). Para texto puro, retorna ``None`` (root = cwd,
    não usado pela fronteira em fontes de texto).

    Args:
        source: Caminho fornecido pelo usuário.
        root: Raiz informada via ``--root``/config (ou ``None``).

    Returns:
        Raiz efetiva (``Path``) ou ``None`` quando a fonte é texto.
    """
    if root is not None:
        return root
    candidate = Path(source)
    if candidate.suffix:
        return candidate.parent
    resolved = candidate.resolve()
    if resolved.exists():
        return resolved.parent
    return None


def _cmd_hash(
    source: str,
    algorithm: str,
    root: Path | None,
    settings: Settings,
) -> int:
    """Executar o comando ``hash``."""
    result = compute(
        source,
        algorithm,
        chunk_size=settings.chunk_size,
        encoding=settings.encoding,
        allowed_root=_resolve_root(source, root),
    )
    logger.info(
        "hash %s de %s (%s): %s",
        result.algorithm,
        result.source,
        result.size_bytes if result.size_bytes is not None else "?",
        result.hexdigest,
    )
    print(result.hexdigest)
    return 0


def _cmd_verify(
    source: str,
    expected: str,
    algorithm: str,
    root: Path | None,
    settings: Settings,
) -> int:
    """Executar o comando ``verify`` (ARES-QA-029).

    Returns:
        ``EXIT_SUCCESS`` (0) quando MATCH,
        ``EXIT_MISMATCH`` (1) quando MISMATCH.
        Erros de domínio/exceções inesperadas sobem para ``main()`` que
        retorna ``EXIT_ERROR`` (2).
    """
    ok = verify_file(
        source,
        expected,
        algorithm,
        chunk_size=settings.chunk_size,
        allowed_root=_resolve_root(source, root),
    )
    if ok:
        print("OK")
        return EXIT_SUCCESS
    print("FAIL")
    return EXIT_MISMATCH


if __name__ == "__main__":
    raise SystemExit(main())
