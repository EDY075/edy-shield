"""CLI real do EDY Shield — comandos ``hash``, ``verify``, ``checksum`` e ``fim``.

Interface via ``argparse`` (stdlib, sem dependências externas). O entrypoint
``edyshield`` do ``pyproject.toml`` aponta para :func:`main`, resolvendo o
achado ARES-QA-021.

Comandos:
    edyshield hash <path> [--algorithm SHA256] [--root DIR]
    edyshield hash --batch <dir> [--recursive] [--algorithm SHA256] [--root DIR]
    edyshield verify <path> --expected <HASH> [--algorithm SHA256] [--root DIR]
    edyshield checksum create <dir> [--algorithm SHA256] [--output FILE] [--recursive]
    edyshield checksum verify <file.sha256|.md5|...> [--root DIR]
    edyshield fim baseline criar <dir> [--algorithm SHA256] [--output baseline.json]
    edyshield fim scan <dir> --baseline <ID|arquivo.json> [--no-recursive]
    edyshield --help
    edyshield --version

Exit codes (ARES-QA-029):
    0 = sucesso total (fim scan: nenhuma mudança)
    1 = mismatch encontrado (verify / checksum verify / fim scan: mudanças)
    2 = erro de uso, domínio ou leitura
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from app import __version__
from app.core.algorithms import compute, hash_directory, hash_files, verify_file
from app.core.checksums import create_checksum_file, verify_checksum_file
from app.core.config import Settings, load_settings
from app.core.exceptions import EDYShieldError
from app.core.fim import (
    DEFAULT_FIM_DIR,
    Baseline,
    FimStore,
    compare_baseline_snapshot,
    create_baseline,
    load_baseline,
    save_baseline,
    scan_snapshot,
)
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
        help="calcular o hash de um arquivo, texto ou diretório (batch)",
        description="Calcula o hash de um arquivo, texto ou diretório (com --batch).",
    )
    hash_parser.add_argument("source", help="caminho do arquivo, texto ou diretório")
    hash_parser.add_argument(
        "--batch",
        action="store_true",
        help="processar um diretório inteiro (vários arquivos)",
    )
    hash_parser.add_argument(
        "--recursive",
        action="store_true",
        help="descer recursivamente em subdiretórios (com --batch)",
    )
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

    checksum_parser = subparsers.add_parser(
        "checksum",
        help="criar e verificar arquivos de checksum",
        description="Cria ou verifica arquivos de checksum (.sha256, .sha1, .md5).",
    )
    checksum_sub = checksum_parser.add_subparsers(dest="checksum_command", required=True)

    create_parser = checksum_sub.add_parser(
        "create",
        help="criar um arquivo de checksum a partir de um diretório",
        description="Gera um arquivo de checksum para todos os arquivos do diretório.",
    )
    create_parser.add_argument("directory", help="diretório a varrer")
    create_parser.add_argument(
        "--algorithm",
        choices=_ALGORITHM_CHOICES,
        default=None,
        help="algoritmo de hash (padrão: configuração ou SHA256)",
    )
    create_parser.add_argument(
        "--output",
        default=None,
        help="arquivo de checksum de saída (padrão: <dir>/SHA256SUMS)",
    )
    create_parser.add_argument(
        "--recursive",
        action="store_true",
        help="descer recursivamente em subdiretórios",
    )
    create_parser.add_argument(
        "--root",
        default=None,
        help="diretório raiz permitido (padrão: diretório alvo)",
    )

    verify_cs_parser = checksum_sub.add_parser(
        "verify",
        help="verificar um arquivo de checksum",
        description="Verifica as entradas de um arquivo de checksum contra os arquivos.",
    )
    verify_cs_parser.add_argument("checksum_file", help="arquivo de checksum (.sha256/.sha1/.md5)")
    verify_cs_parser.add_argument(
        "--root",
        default=None,
        help="diretório raiz permitido (padrão: diretório do checksum)",
    )

    fim_parser = subparsers.add_parser(
        "fim",
        help="File Integrity Monitor — baseline e detecção de mudanças",
        description="Cria baselines de integridade e compara contra varreduras posteriores.",
    )
    fim_sub = fim_parser.add_subparsers(dest="fim_command", required=True)

    baseline_parser = fim_sub.add_parser(
        "baseline",
        help="criar uma baseline de integridade do diretório/arquivo",
        description="Fotografia criptográfica (hashes + metadados) do alvo.",
    )
    baseline_sub = baseline_parser.add_subparsers(dest="baseline_command", required=True)

    criar_parser = baseline_sub.add_parser(
        "criar",
        help="criar uma baseline e salvar como JSON",
        description="Gera a baseline (baseline.json por padrão) e registra no FimStore.",
    )
    criar_parser.add_argument("target", help="diretório ou arquivo a fotografar")
    criar_parser.add_argument(
        "--algorithm",
        choices=_ALGORITHM_CHOICES,
        default=None,
        help="algoritmo de hash (padrão: configuração ou SHA256)",
    )
    criar_parser.add_argument(
        "--no-recursive",
        action="store_true",
        help="não descer recursivamente em subdiretórios",
    )
    criar_parser.add_argument(
        "--output",
        default="baseline.json",
        help="arquivo JSON de saída (padrão: baseline.json)",
    )

    scan_parser = fim_sub.add_parser(
        "scan",
        help="varrer o alvo e comparar contra uma baseline",
        description="Detecta arquivos novos, modificados e removidos.",
    )
    scan_parser.add_argument("target", help="diretório ou arquivo a varrer")
    scan_parser.add_argument(
        "--baseline",
        required=True,
        help="baseline_id (fim_...) ou caminho de arquivo JSON",
    )
    scan_parser.add_argument(
        "--algorithm",
        choices=_ALGORITHM_CHOICES,
        default=None,
        help="algoritmo de hash (padrão: da baseline)",
    )
    scan_parser.add_argument(
        "--no-recursive",
        action="store_true",
        help="não descer recursivamente em subdiretórios",
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
        - ``1`` verificação MISMATCH (verify / checksum verify)
        - ``2`` erro de uso, domínio ou leitura
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

    algorithm = getattr(args, "algorithm", None) or settings.default_hash_algorithm
    # Prioridade de raiz permitida (ARES-QA-028): --root explícito > env
    # EDY_ALLOWED_ROOT > diretório pai do arquivo alvo (resolvido).
    if getattr(args, "root", None):
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
            if args.batch:
                return _cmd_hash_batch(args.source, algorithm, args.recursive)
            return _cmd_hash(args.source, algorithm, root, settings)
        if args.command == "verify":
            return _cmd_verify(args.source, args.expected, algorithm, root, settings)
        if args.command == "checksum":
            if args.checksum_command == "create":
                return _cmd_checksum_create(args.directory, algorithm, args.output, args.recursive)
            if args.checksum_command == "verify":
                return _cmd_checksum_verify(args.checksum_file, root, settings)
        if args.command == "fim":
            if args.fim_command == "baseline" and args.baseline_command == "criar":
                return _cmd_fim_baseline_criar(
                    args.target, algorithm, args.output, args.no_recursive
                )
            if args.fim_command == "scan":
                return _cmd_fim_scan(
                    args.target,
                    args.baseline,
                    algorithm if args.algorithm else None,
                    args.no_recursive,
                )
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
    """Executar o comando ``hash`` (arquivo ou texto)."""
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
    return EXIT_SUCCESS


def _cmd_hash_batch(
    source: str,
    algorithm: str,
    recursive: bool,
) -> int:
    """Executar o comando ``hash --batch`` (diretório/lista de arquivos).

    Resultados (digests) vão para stdout; erros individuais e resumo vão para
    stderr. Exit code ``2`` se algum arquivo falhar, ``0`` se tudo passar.

    Args:
        source: Diretório (ou arquivo) a processar em lote.
        algorithm: Algoritmo de hash.
        recursive: Se ``True``, varre recursivamente subdiretórios.

    Returns:
        Código de saída (0 sucesso total, 2 com erros).
    """
    path = Path(source)
    if path.is_dir():
        results = hash_directory(path, algorithm, recursive=recursive)
    else:
        results = hash_files([path], algorithm)

    ok = 0
    errors = 0
    for entry, err in results:
        if err is not None or entry is None:
            errors += 1
            print(f"erro: {err}", file=sys.stderr)
            continue
        ok += 1
        print(f"{entry.hexdigest}  {entry.path}")

    print(
        f"batch: {len(results)} processado(s), {ok} sucesso(s), {errors} erro(s)",
        file=sys.stderr,
    )
    return EXIT_SUCCESS if errors == 0 else EXIT_ERROR


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


def _default_checksum_output(directory: Path, algorithm: str) -> Path:
    """Nome padrão do arquivo de checksum para um algoritmo."""
    suffix = {"SHA256": "SHA256SUMS", "SHA1": "SHA1SUMS", "MD5": "MD5SUMS"}[algorithm]
    return directory / suffix


def _cmd_checksum_create(
    directory: str,
    algorithm: str,
    output: str | None,
    recursive: bool,
) -> int:
    """Executar o comando ``checksum create``.

    Args:
        directory: Diretório a varrer.
        algorithm: Algoritmo de hash.
        output: Caminho do arquivo de checksum (ou ``None`` para padrão).
        recursive: Se ``True``, desce recursivamente.

    Returns:
        ``EXIT_SUCCESS`` (0) ou ``EXIT_ERROR`` (2).
    """
    root = Path(directory)
    out_path = (
        Path(output).resolve() if output else _default_checksum_output(root.resolve(), algorithm)
    )

    count = create_checksum_file(root, out_path, algorithm=algorithm, recursive=recursive)
    print(f"checksum criado: {out_path} ({count} entrada(s))")
    return EXIT_SUCCESS


def _cmd_checksum_verify(
    checksum_file: str,
    root: Path | None,
    settings: Settings,
) -> int:
    """Executar o comando ``checksum verify``.

    Para cada entrada, imprime ``status  filename``. Ao final imprime resumo.
    Exit code: ``0`` se tudo OK, ``1`` se houver mismatch/missing/invalid.

    Args:
        checksum_file: Caminho do arquivo de checksum.
        root: Raiz permitida (ou ``None`` para o diretório do arquivo).
        settings: Configurações carregadas.

    Returns:
        Código de saída (0, 1 ou 2).
    """
    allowed_root = root.resolve() if root is not None else None
    report = verify_checksum_file(
        checksum_file, allowed_root=allowed_root, chunk_size=settings.chunk_size
    )

    for entry in report.entries:
        if entry.status == "ok":
            print(f"ok       {entry.filename}")
        elif entry.status == "mismatch":
            print(f"mismatch {entry.filename}")
        elif entry.status == "missing":
            print(f"missing  {entry.filename}")
        else:
            print(f"invalid  {entry.filename}  ({entry.error})")

    print(
        f"checksum: {report.ok}/{report.total} ok, "
        f"{report.mismatch} mismatch, {report.missing} missing, "
        f"{report.invalid} invalid",
        file=sys.stderr,
    )

    if report.ok_all:
        return EXIT_SUCCESS
    return EXIT_MISMATCH


def _cmd_fim_baseline_criar(
    target: str,
    algorithm: str,
    output: str,
    no_recursive: bool,
) -> int:
    """Executar o comando ``fim baseline criar`` (Sprint 5).

    Cria a baseline de integridade do alvo, salva como JSON determinístico
    (``--output``, padrão ``baseline.json``) e registra no FimStore
    (``~/.edyshield/fim``) para reutilização por id.

    Args:
        target: Diretório ou arquivo a fotografar.
        algorithm: Algoritmo de hash.
        output: Caminho do arquivo JSON de saída.
        no_recursive: Quando ``True``, não desce em subdiretórios.

    Returns:
        ``EXIT_SUCCESS`` (0) ou ``EXIT_ERROR`` (2).
    """
    baseline = create_baseline(
        target,
        algorithm=algorithm,
        recursive=not no_recursive,
        allowed_root=None,
    )
    # Persistência dupla: FimStore (id) + arquivo JSON local.
    store = FimStore(DEFAULT_FIM_DIR)
    baseline_id = store.save(baseline)
    out_path = save_baseline(baseline, output)

    print(f"baseline criada: {out_path} ({len(baseline.entries)} entrada(s)) — id {baseline_id}")
    return EXIT_SUCCESS


def _load_baseline_cli(reference: str) -> Baseline:
    """Carregar uma baseline por id do FimStore ou por caminho de arquivo.

    Args:
        reference: ``fim_...`` (id no store) ou caminho de arquivo JSON.

    Returns:
        :class:`~app.core.fim.models.Baseline`.

    Raises:
        EDYShieldError / FileNotFoundError: Se a baseline não for localizada.
    """
    store = FimStore(DEFAULT_FIM_DIR)
    is_id = reference.startswith("fim_") and "/" not in reference and "\\" not in reference
    if is_id:
        try:
            return store.load(reference)
        except EDYShieldError:
            pass
    return load_baseline(reference)


def _cmd_fim_scan(
    target: str,
    baseline_ref: str,
    algorithm: str | None,
    no_recursive: bool,
) -> int:
    """Executar o comando ``fim scan`` (Sprint 5).

    Carrega a baseline de referência, re-varrer o alvo e compara. Imprime
    as mudanças detectadas e um resumo.

    Args:
        target: Diretório ou arquivo a varrer.
        baseline_ref: baseline_id (``fim_...``) ou caminho de arquivo JSON.
        algorithm: Algoritmo (``None`` usa o da baseline).
        no_recursive: Quando ``True``, não desce em subdiretórios.

    Returns:
        ``EXIT_SUCCESS`` (0) quando sem mudanças, ``EXIT_MISMATCH`` (1)
        quando há mudanças, ``EXIT_ERROR`` (2) em falhas.
    """
    baseline = _load_baseline_cli(baseline_ref)
    effective_algorithm = algorithm or baseline.algorithm

    snapshot = scan_snapshot(
        target,
        algorithm=effective_algorithm,
        recursive=not no_recursive,
        allowed_root=None,
    )
    diff = compare_baseline_snapshot(baseline, snapshot)

    for path in diff.added:
        print(f"novo       {path}")
    for path in diff.modified:
        print(f"modificado {path}")
    for path in diff.removed:
        print(f"removido   {path}")
    for path in diff.ignored:
        print(f"ignorado   {path}", file=sys.stderr)

    print(
        f"fim: {diff.changed} mudança(s) — "
        f"{len(diff.added)} novo(s), {len(diff.modified)} modificado(s), "
        f"{len(diff.removed)} removido(s), {len(diff.unchanged)} inalterado(s)",
        file=sys.stderr,
    )
    return EXIT_MISMATCH if diff.changed else EXIT_SUCCESS


if __name__ == "__main__":
    raise SystemExit(main())
