"""CLI de alertas do EDY Shield -- comando ``edyshield alerts`` (M3-T09).

Subcomandos:

    edyshield alerts list [--severity HIGH] [--status NEW] [--source fim]
                          [--limit 50] [--offset 0] [--json]
    edyshield alerts show <alert_id> [--json]
    edyshield alerts ack <alert_id> [--by USER] [--note TEXT]
    edyshield alerts resolve <alert_id> [--by USER] [--note TEXT]
    edyshield alerts suppress <alert_id> [--reason TEXT]
    edyshield alerts stats [--json]
    edyshield alerts rules [--json]

Consumir apenas o :class:`~app.services.alert_service.AlertService`;
nenhuma logica de negocio vive aqui (SPRINT/ADR-002).

Exit codes (ARES-QA-029):
    0 = sucesso
    1 = alerta nao encontrado ou transicao invalida
    2 = erro de uso
"""

from __future__ import annotations

import argparse
import json
import sys

from app.core.alerts.models import AlertStatus, Severity
from app.core.logging import get_logger
from app.services.alert_service import AlertService, AlertServiceError

_logger = get_logger("cli.alert_cmd")


def _build_alerts_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """Construir o subparser ``alerts`` com seus subcomandos."""
    alerts_parser = subparsers.add_parser(
        "alerts",
        help="gerenciar alertas do motor de alertas",
        description="Gerencia alertas: listar, detalhar, ack, resolve, suppress, stats e regras.",
    )
    alerts_sub = alerts_parser.add_subparsers(dest="alert_command", required=True)

    # list
    list_parser = alerts_sub.add_parser(
        "list",
        help="listar alertas com filtros",
        description="Lista alertas com filtros opcionais (mais recentes primeiro).",
    )
    list_parser.add_argument(
        "--severity",
        choices=[s.value for s in Severity],
        help="filtrar por severidade",
    )
    list_parser.add_argument(
        "--status",
        choices=[s.value for s in AlertStatus],
        help="filtrar por status",
    )
    list_parser.add_argument("--source", help="filtrar por origem")
    list_parser.add_argument(
        "--limit", type=int, default=50, help="maximo de resultados (default 50)"
    )
    list_parser.add_argument("--offset", type=int, default=0, help="deslocamento para paginacao")
    list_parser.add_argument("--json", action="store_true", dest="as_json", help="saida em JSON")

    # show
    show_parser = alerts_sub.add_parser(
        "show",
        help="detalhar um alerta por ID",
        description="Mostra detalhes completos de um alerta especifico.",
    )
    show_parser.add_argument("alert_id", help="ID do alerta")
    show_parser.add_argument("--json", action="store_true", dest="as_json", help="saida em JSON")

    # ack
    ack_parser = alerts_sub.add_parser(
        "ack",
        help="reconhecer um alerta (ACKNOWLEDGED)",
        description="Marca um alerta como reconhecido.",
    )
    ack_parser.add_argument("alert_id", help="ID do alerta")
    ack_parser.add_argument("--by", default="cli", help="usuario que reconheceu (default: cli)")
    ack_parser.add_argument("--note", default="", help="nota de reconhecimento")

    # resolve
    resolve_parser = alerts_sub.add_parser(
        "resolve",
        help="resolver um alerta (RESOLVED)",
        description="Marca um alerta como resolvido.",
    )
    resolve_parser.add_argument("alert_id", help="ID do alerta")
    resolve_parser.add_argument("--by", default="cli", help="usuario que resolveu (default: cli)")
    resolve_parser.add_argument("--note", default="", help="nota de resolucao")

    # suppress
    suppress_parser = alerts_sub.add_parser(
        "suppress",
        help="suprimir um alerta (SUPPRESSED)",
        description="Marca um alerta como suprimido.",
    )
    suppress_parser.add_argument("alert_id", help="ID do alerta")
    suppress_parser.add_argument("--reason", default="", help="motivo da supressao")

    # reopen
    reopen_parser = alerts_sub.add_parser(
        "reopen",
        help="reabrir um alerta (NEW)",
        description="Reabre um alerta resolvido ou suprimido.",
    )
    reopen_parser.add_argument("alert_id", help="ID do alerta")
    reopen_parser.add_argument("--reason", default="", help="motivo da reabertura")

    # stats
    stats_parser = alerts_sub.add_parser(
        "stats",
        help="estatisticas de alertas",
        description="Mostra agregacoes e estatisticas dos alertas.",
    )
    stats_parser.add_argument("--json", action="store_true", dest="as_json", help="saida em JSON")

    # rules
    rules_parser = alerts_sub.add_parser(
        "rules",
        help="listar regras ativas do motor",
        description="Lista todas as regras de alerta registradas no engine.",
    )
    rules_parser.add_argument("--json", action="store_true", dest="as_json", help="saida em JSON")


def handle_alerts_command(args: argparse.Namespace) -> int:
    """Processar o comando ``alerts`` e seus subcomandos.

    Args:
        args: Namespace do argparse com ``alert_command`` definido.

    Returns:
        Exit code (0=sucesso, 1=alerta nao encontrado/invalido, 2=erro uso).
    """
    sub = getattr(args, "alert_command", None)
    if sub is None:
        print(
            "Erro: subcomando `alerts` requer uma acao (list|show|ack|resolve|suppress|reopen|stats|rules)",
            file=sys.stderr,
        )
        return 2

    try:
        service = AlertService()
    except Exception as exc:
        print(f"Erro ao inicializar servico de alertas: {exc}", file=sys.stderr)
        return 2

    try:
        if sub == "list":
            return _handle_list(service, args)
        if sub == "show":
            return _handle_show(service, args)
        if sub == "ack":
            return _handle_ack(service, args)
        if sub == "resolve":
            return _handle_resolve(service, args)
        if sub == "suppress":
            return _handle_suppress(service, args)
        if sub == "reopen":
            return _handle_reopen(service, args)
        if sub == "stats":
            return _handle_stats(service, args)
        if sub == "rules":
            return _handle_rules(service, args)
        print(f"Subcomando desconhecido: {sub}", file=sys.stderr)
        return 2
    except AlertServiceError as exc:
        print(f"Erro: {exc}", file=sys.stderr)
        return 1
    finally:
        service.close()


def _handle_list(service: AlertService, args: argparse.Namespace) -> int:
    severity = Severity(args.severity) if args.severity else None
    status = AlertStatus(args.status) if args.status else None
    alerts = service.list_alerts(
        severity=severity,
        status=status,
        source=args.source,
        limit=args.limit,
        offset=args.offset,
    )
    if getattr(args, "as_json", False):
        payload = [a.to_dict() for a in alerts]
        print(json.dumps(payload, indent=2, ensure_ascii=False, default=str))
        return 0

    if not alerts:
        print("Nenhum alerta encontrado.")
        return 0

    # Tabela compacta
    print(f"{'ID':<18} {'SEVER':<8} {'STATUS':<13} {'SOURCE':<20} {'COUNT':>5} {'TITLE'}")
    print("-" * 100)
    for a in alerts:
        print(
            f"{a.alert_id:<18} {a.severity.value:<8} {a.status.value:<13} "
            f"{a.source:<20} {a.count:>5} {a.title}"
        )
    print(f"\nTotal: {len(alerts)} alerta(s).")
    return 0


def _handle_show(service: AlertService, args: argparse.Namespace) -> int:
    record = service.get_alert(args.alert_id)
    if record is None:
        print(f"Alerta nao encontrado: {args.alert_id}", file=sys.stderr)
        return 1

    if getattr(args, "as_json", False):
        print(json.dumps(record.to_dict(), indent=2, ensure_ascii=False, default=str))
        return 0

    d = record.to_dict()
    print(f"Alerta:      {d['alert_id']}")
    print(f"Severidade:  {d['severity']}")
    print(f"Status:      {d['status']}")
    print(f"Origem:      {d['source']}")
    print(f"Regra:       {d['rule_id']}")
    print(f"Alvo:        {d['target']}")
    print(f"Titulo:      {d['title']}")
    print(f"Descricao:   {d['description']}")
    print(f"Contagem:    {d['count']}")
    print(f"First seen:  {d['first_seen_at']}")
    print(f"Last seen:   {d['last_seen_at']}")
    if d.get("acknowledged_at"):
        print(f"ACK por:     {d.get('acknowledged_by', 'N/A')} em {d['acknowledged_at']}")
    if d.get("resolved_at"):
        print(f"Resolvido:   {d.get('resolved_by', 'N/A')} em {d['resolved_at']}")
    if d.get("resolution_note"):
        print(f"Nota:        {d['resolution_note']}")
    print(f"Fingerprint: {d['fingerprint'][:16]}...")
    return 0


def _handle_ack(service: AlertService, args: argparse.Namespace) -> int:
    record = service.acknowledge_alert(args.alert_id, acked_by=args.by, note=args.note)
    print(f"Alerta {record.alert_id} reconhecido por {args.by}.")
    return 0


def _handle_resolve(service: AlertService, args: argparse.Namespace) -> int:
    record = service.resolve_alert(args.alert_id, resolved_by=args.by, resolution_note=args.note)
    print(f"Alerta {record.alert_id} resolvido por {args.by}.")
    return 0


def _handle_suppress(service: AlertService, args: argparse.Namespace) -> int:
    record = service.suppress_alert(args.alert_id, reason=args.reason)
    print(f"Alerta {record.alert_id} suprimido.")
    return 0


def _handle_reopen(service: AlertService, args: argparse.Namespace) -> int:
    record = service.reopen_alert(args.alert_id, reason=args.reason)
    print(f"Alerta {record.alert_id} reaberto.")
    return 0


def _handle_stats(service: AlertService, args: argparse.Namespace) -> int:
    stats = service.stats()
    if getattr(args, "as_json", False):
        print(json.dumps(stats, indent=2, ensure_ascii=False, default=str))
        return 0

    print("=== Estatisticas de Alertas ===")
    store = stats.get("store", {})
    print(f"Total persistido: {store.get('total', 0)}")
    print()
    by_status = store.get("by_status", {})
    if by_status:
        print("Por Status:")
        for s, c in sorted(by_status.items()):
            print(f"  {s:<15} {c}")
    print()
    by_sev = store.get("by_severity", {})
    if by_sev:
        print("Por Severidade:")
        for s, c in sorted(by_sev.items()):
            print(f"  {s:<10} {c}")
    print()
    by_src = store.get("by_source", {})
    if by_src:
        print("Por Origem:")
        for s, c in sorted(by_src.items()):
            print(f"  {s:<20} {c}")
    print()
    engine = stats.get("engine", {})
    print("Engine:")
    for k, v in sorted(engine.items()):
        print(f"  {k:<25} {v}")
    print(f"  {'dedup_cache_size':<25} {stats.get('dedup_cache_size', 0)}")
    return 0


def _handle_rules(service: AlertService, args: argparse.Namespace) -> int:
    rules = service.list_rules()
    if getattr(args, "as_json", False):
        payload = [
            {
                "rule_id": r.rule_id,
                "name": r.name,
                "source": r.source,
                "condition_key": r.condition_key,
                "operator": r.operator,
                "condition_value": r.condition_value,
                "target_severity": r.target_severity.value,
                "enabled": r.enabled,
                "priority": r.priority,
                "suppression_window_seconds": r.suppression_window_seconds,
            }
            for r in rules
        ]
        print(json.dumps(payload, indent=2, ensure_ascii=False, default=str))
        return 0

    if not rules:
        print("Nenhuma regra registrada.")
        return 0

    print(f"{'ID':<20} {'NAME':<30} {'SOURCE':<18} {'SEVER':<8} {'ENBL':>4} {'PRIO':>4}")
    print("-" * 90)
    for r in rules:
        enabled = "Y" if r.enabled else "N"
        print(
            f"{r.rule_id:<20} {r.name[:30]:<30} {r.source:<18} "
            f"{r.target_severity.value:<8} {enabled:>4} {r.priority:>4}"
        )
    print(f"\nTotal: {len(rules)} regra(s).")
    return 0
