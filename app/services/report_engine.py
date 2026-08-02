"""Report Engine — transforma ScanResult em relatórios (Sprint 3, Missão 8).

Camada de casos de uso: converte qualquer :class:`ScanResult` (produzido por
um plugin via PluginManager) em relatórios portáveis:

* **JSON** — estrutura completa e máquina-legível.
* **TXT** — relatório legível em texto puro.
* **HTML** — relatório estilizado para visualização em navegador.

Estrutura comum a todos os formatos (Missão 8):

* Resumo (``summary``)
* Achados/Evidências (``findings``)
* Severidade máxima (``max_severity``)
* Timestamp UTC (``timestamp``)
* Versão (``plugin_version``)
* Observações (``observations``)

**Sem PDF** — fora do escopo da Missão 8 (roadmap futura).

Segurança: saídas HTML são **escapadas** (``html.escape``) para evitar
injeção de conteúdo quando o relatório é aberto em navegador — evidências
vêm de logs/arquivos não confiáveis (OPSEC).
"""

from __future__ import annotations

import html
import json
from datetime import UTC

from app.plugins.contracts import ScanResult

#: Mapeamento de severidade para rótulos/badges (PT-BR).
_SEVERITY_LABELS: dict[str, str] = {
    "INFO": "Info",
    "LOW": "Baixa",
    "MEDIUM": "Média",
    "HIGH": "Alta",
    "CRITICAL": "Crítica",
}

#: Cores CSS por severidade (badges do relatório HTML).
_SEVERITY_COLORS: dict[str, str] = {
    "INFO": "#8b949e",
    "LOW": "#f0b90b",
    "MEDIUM": "#f0883e",
    "HIGH": "#ff4d4d",
    "CRITICAL": "#ff2d55",
}


def to_json(result: ScanResult, *, pretty: bool = True) -> str:
    """Converter um ScanResult em JSON.

    Args:
        result: Resultado a serializar.
        pretty: Quando ``True`` (padrão), formata com indentação de 2.

    Returns:
        String JSON com timestamp em ISO 8601 UTC.
    """
    data = result.as_dict()
    if pretty:
        return json.dumps(data, indent=2, ensure_ascii=False)
    return json.dumps(data, ensure_ascii=False)


def to_txt(result: ScanResult) -> str:
    """Converter um ScanResult em relatório de texto puro.

    Args:
        result: Resultado a serializar.

    Returns:
        Relatório TXT legível.
    """
    lines: list[str] = [
        "=" * 64,
        "EDY SHIELD — RELATÓRIO DE VARREDURA",
        "=" * 64,
        f"Plugin      : {result.plugin_name} v{result.plugin_version}",
        f"Timestamp   : {result.timestamp.astimezone(UTC).isoformat()}",
        f"Severidade  : {_SEVERITY_LABELS.get(result.max_severity().value, result.max_severity().value)}",
        "",
        "RESUMO",
        "-" * 64,
        result.summary,
        "",
        "ESTATÍSTICAS",
        "-" * 64,
    ]
    if result.stats:
        for key, value in sorted(result.stats.items()):
            lines.append(f"{key:<20}: {value}")
    else:
        lines.append("(sem estatísticas)")

    lines += ["", "ACHADOS", "-" * 64]
    if result.findings:
        for index, finding in enumerate(result.findings, start=1):
            severity_label = _SEVERITY_LABELS.get(finding.severity.value, finding.severity.value)
            source = f" [{finding.source}]" if finding.source else ""
            lines.append(f"{index:>2}. [{severity_label}]{source} {finding.message}")
    else:
        lines.append("(nenhum achado)")

    lines += ["", "OBSERVAÇÕES", "-" * 64]
    if result.observations:
        lines.extend(f"- {observation}" for observation in result.observations)
    else:
        lines.append("(nenhuma observação)")

    lines += ["", "=" * 64]
    return "\n".join(lines) + "\n"


def to_html(result: ScanResult) -> str:
    """Converter um ScanResult em relatório HTML autônomo.

    Todo conteúdo dinâmico é escapado (``html.escape``) — nunca confie em
    conteúdo de logs para HTML cru (prevenção de XSS/HTML injection).

    Args:
        result: Resultado a serializar.

    Returns:
        Documento HTML completo (standalone, dark theme).
    """
    severity = result.max_severity().value
    severity_label = _SEVERITY_LABELS.get(severity, severity)
    color = _SEVERITY_COLORS.get(severity, "#8b949e")

    findings_html = ""
    if result.findings:
        items = []
        for finding in result.findings:
            sev = finding.severity.value
            sev_label = _SEVERITY_LABELS.get(sev, sev)
            sev_color = _SEVERITY_COLORS.get(sev, "#8b949e")
            source = (
                f'<span class="src">{html.escape(finding.source)}</span>' if finding.source else ""
            )
            items.append(
                f'<li><span class="badge" style="background:{sev_color}">{sev_label}</span>'
                f"{source} {html.escape(finding.message)}</li>"
            )
        findings_html = "<ul>" + "".join(items) + "</ul>"
    else:
        findings_html = '<p class="empty">Nenhum achado.</p>'

    stats_html = ""
    if result.stats:
        cells = "".join(
            f"<tr><td>{html.escape(key)}</td><td>{value}</td></tr>"
            for key, value in sorted(result.stats.items())
        )
        stats_html = f"<table><tbody>{cells}</tbody></table>"
    else:
        stats_html = '<p class="empty">Sem estatísticas.</p>'

    observations_html = (
        "".join(f"<li>{html.escape(observation)}</li>" for observation in result.observations)
        or '<p class="empty">Nenhuma observação.</p>'
    )

    return (
        "<!DOCTYPE html>\n"
        '<html lang="pt-BR">\n'
        "<head>\n"
        '  <meta charset="UTF-8">\n'
        "  <title>EDY Shield — Relatório de Varredura</title>\n"
        "  <style>\n"
        "    :root { color-scheme: dark; }\n"
        "    body { font-family: 'Inter', system-ui, sans-serif; background: #0a0e14;"
        " color: #e6edf3; margin: 0; padding: 32px; }\n"
        "    .wrap { max-width: 860px; margin: 0 auto; }\n"
        "    h1 { font-size: 1.5rem; border-bottom: 1px solid #1f2633; padding-bottom: 12px; }\n"
        "    h2 { font-size: 1.05rem; margin-top: 28px; color: #22d3ee; text-transform: uppercase;"
        " letter-spacing: 0.08em; }\n"
        "    .meta { color: #8b949e; font-size: 0.9rem; line-height: 1.7; }\n"
        "    .summary { background: #12161f; border: 1px solid #1f2633; border-radius: 10px;"
        " padding: 16px 18px; }\n"
        "    ul { list-style: none; padding: 0; }\n"
        "    li { padding: 8px 0; border-bottom: 1px solid #161c28; }\n"
        "    .badge { display: inline-block; padding: 2px 10px; border-radius: 999px;"
        " font-size: 0.72rem; font-weight: 700; color: #0a0e14; margin-right: 8px; }\n"
        "    .src { font-family: 'JetBrains Mono', monospace; font-size: 0.78rem;"
        " color: #8b949e; margin-right: 8px; }\n"
        "    table { width: 100%; border-collapse: collapse; }\n"
        "    td { padding: 6px 10px; border: 1px solid #1f2633; font-family: 'JetBrains Mono', monospace;"
        " font-size: 0.85rem; }\n"
        "    .empty { color: #6e7681; }\n"
        "    footer { margin-top: 40px; color: #6e7681; font-size: 0.78rem;"
        " border-top: 1px solid #1f2633; padding-top: 12px; }\n"
        "  </style>\n"
        "</head>\n"
        "<body>\n"
        '  <div class="wrap">\n'
        f"    <h1>EDY Shield — Relatório de Varredura</h1>\n"
        '    <div class="meta">\n'
        f"      <div>Plugin: <strong>{html.escape(result.plugin_name)}</strong> "
        f"v{html.escape(result.plugin_version)}</div>\n"
        f"      <div>Timestamp: {result.timestamp.astimezone(UTC).isoformat()}</div>\n"
        f'      <div>Severidade máxima: <span class="badge" style="background:{color}">'
        f"{severity_label}</span></div>\n"
        "    </div>\n"
        "    <h2>Resumo</h2>\n"
        f'    <div class="summary">{html.escape(result.summary)}</div>\n'
        "    <h2>Estatísticas</h2>\n"
        f"    {stats_html}\n"
        "    <h2>Achados</h2>\n"
        f"    {findings_html}\n"
        "    <h2>Observações</h2>\n"
        f"    <ul>{observations_html}</ul>\n"
        "    <footer>EDY Shield — relatório gerado automaticamente. "
        "Defenda. Verifique. Confie.</footer>\n"
        "  </div>\n"
        "</body>\n"
        "</html>\n"
    )


def render(result: ScanResult, fmt: str) -> str:
    """Renderizar um ScanResult no formato solicitado.

    Args:
        result: Resultado a renderizar.
        fmt: Formato desejado — ``json``, ``txt`` ou ``html``.

    Returns:
        Conteúdo do relatório no formato escolhido.

    Raises:
        ValueError: Se ``fmt`` não for suportado.
    """
    normalized = fmt.strip().lower()
    if normalized == "json":
        return to_json(result)
    if normalized == "txt":
        return to_txt(result)
    if normalized == "html":
        return to_html(result)
    raise ValueError(f"Formato de relatório não suportado: {fmt!r}. Use json|txt|html.")
