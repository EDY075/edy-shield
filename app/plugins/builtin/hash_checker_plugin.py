"""Hash Checker como plugin oficial do EDY Shield (Sprint 3, Missão 9).

Envolve a API pública do Core (:mod:`app.core.algorithms`) como um
:class:`Plugin`, para que a **UI consuma o Hash Checker via PluginManager**
— a mesma via de todos os demais módulos. Nenhuma lógica de negócio fica
na interface (Missão 9).

O plugin aceita no ``ScanContext``:

* ``target`` — texto (hash como texto) ou caminho de arquivo (hash de
  arquivo). Strings que parecem caminhos são tratadas como arquivo pelo
  Core (ARES-QA-002).
* ``options["algorithm"]`` — ``SHA256`` (padrão), ``SHA1`` ou ``MD5``.
* ``options["encoding"]`` — encoding de texto (padrão ``utf-8``).
* ``options["expected"]`` — digest esperado; quando presente, gera um
  achado de verificação (MATCH/MISMATCH).
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from app.core.algorithms import (
    DEFAULT_CHUNK_SIZE,
    compute,
    verify_file,
)
from app.core.config.settings import DEFAULT_ENCODING
from app.core.crypto import normalize_algorithm, safe_compare
from app.core.exceptions import EDYShieldError
from app.core.filesystem.safe_path import resolve_safe_path
from app.plugins.contracts import Evidence, ScanContext, ScanResult, Severity
from app.plugins.plugin_base import Plugin
from app.plugins.plugin_errors import PluginExecutionError


class HashCheckerPlugin(Plugin):
    """Plugin que calcula e verifica hashes usando o Core do EDY Shield."""

    name = "hash_checker"
    version = "1.1.0"
    description = (
        "Calcula hashes criptográficos (SHA-256, SHA-1, MD5) de texto ou "
        "arquivo e verifica integridade contra um digest esperado."
    )
    author = "EDY Shield Contributors"

    def validate(self, context: ScanContext) -> None:
        """Validar o contexto antes da execução.

        Args:
            context: Contexto com ``target`` e ``options``.

        Raises:
            PluginExecutionError: Se ``target`` estiver ausente ou o
                algoritmo for inválido.
        """
        if context.target is None:
            raise PluginExecutionError(
                "Hash Checker exige texto ou arquivo como target.",
                plugin_name=self.name,
            )
        try:
            normalize_algorithm(context.options.get("algorithm", "SHA256"))
        except EDYShieldError as exc:
            raise PluginExecutionError(
                f"algoritmo inválido: {exc}",
                plugin_name=self.name,
            ) from exc
        # Caminhos explícitos (Path) são validados na fronteira de segurança
        # (padrão ARES-QA-028 / LogAnalyzer) para rejeitar acesso fora da raiz.
        if isinstance(context.target, Path):
            try:
                resolve_safe_path(
                    context.target,
                    allowed_root=self._effective_root(context.target, context),
                    strict=True,
                )
            except Exception as exc:
                raise PluginExecutionError(
                    f"Hash Checker não pôde acessar o arquivo: {exc}",
                    plugin_name=self.name,
                ) from exc

    def execute(self, context: ScanContext) -> ScanResult:
        """Executar o cálculo/verificação e retornar um ScanResult.

        Args:
            context: Contexto já validado.

        Returns:
            Resultado com o digest, origem e (se solicitado) verificação.
        """
        assert context.target is not None
        algorithm = context.options.get("algorithm", "SHA256")
        encoding = context.options.get("encoding", DEFAULT_ENCODING)
        expected = context.options.get("expected")
        member = normalize_algorithm(algorithm)
        allowed_root = self._effective_root(Path(str(context.target)), context)

        try:
            result = compute(
                context.target,
                member,
                encoding=encoding,
                chunk_size=DEFAULT_CHUNK_SIZE,
                allowed_root=allowed_root,
            )
        except Exception as exc:
            raise PluginExecutionError(
                f"falha ao calcular hash: {exc}",
                plugin_name=self.name,
            ) from exc

        findings: list[Evidence] = [
            Evidence(
                severity=Severity.INFO,
                message=f"Hash {result.algorithm} calculado.",
                metadata={
                    "hexdigest": result.hexdigest,
                    "source": result.source,
                },
            )
        ]

        observations: list[str] = [
            f"Origem: {result.source}",
            f"Tamanho: {result.size_bytes} bytes"
            if result.size_bytes is not None
            else "Tamanho: desconhecido",
        ]

        # Modo verificação: compara contra o digest esperado.
        if expected is not None:
            expected_str = str(expected).strip().lower()
            if result.source == "file" and result.path is not None:
                ok = verify_file(
                    result.path,
                    expected_str,
                    member,
                    chunk_size=DEFAULT_CHUNK_SIZE,
                    allowed_root=allowed_root,
                )
            else:
                ok = safe_compare(result.hexdigest, expected_str)
            match_severity = Severity.INFO if ok else Severity.HIGH
            findings.append(
                Evidence(
                    severity=match_severity,
                    message=(
                        "Verificação de integridade: MATCH."
                        if ok
                        else "Verificação de integridade: MISMATCH."
                    ),
                    metadata={"expected": expected_str},
                )
            )

        return ScanResult(
            plugin_name=self.name,
            plugin_version=self.version,
            timestamp=datetime.now(UTC),
            summary=(
                f"Hash {result.algorithm} calculado com sucesso"
                + (". Verificação: MATCH." if expected is not None and ok else "")
            ),
            findings=tuple(findings),
            stats={"bytes": result.size_bytes} if result.size_bytes is not None else {},
            observations=tuple(observations),
        )

    def health_check(self) -> bool:
        """O plugin está sempre pronto para executar (sem estado externo)."""
        return True

    @staticmethod
    def _effective_root(target: Path, context: ScanContext) -> Path | None:
        """Derivar a raiz permitida para acesso ao arquivo.

        Segue o padrão ARES-QA-028 (adotado também pelo LogAnalyzer):
        quando o chamador não define ``allowed_root``, a raiz passa a ser o
        **diretório pai do arquivo alvo** — permite processar qualquer
        caminho absoluto mantendo a contenção da fronteira.

        Args:
            target: Caminho fornecido pelo usuário.
            context: Contexto da varredura (pode conter ``allowed_root``).

        Returns:
            Raiz efetiva (``Path``) ou ``None`` quando o contexto a define
            como ``None`` (usa cwd — comportamento padrão do Core).
        """
        if context.allowed_root is not None:
            return context.allowed_root
        return target.parent
