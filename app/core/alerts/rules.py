"""Repositorio e avaliador de regras de alerta (EDY Shield -- M3-T05).

O :class:`RuleRegistry` mantem o conjunto de :class:`~app.core.alerts.models.AlertRule`
ativas e avalia eventos contra elas. Regras podem ser:

* **Embutidas** (built-in): definidas no codigo, carregadas em
  :func:`default_rules`.
* **Dinamicas**: adicionadas em runtime via :meth:`RuleRegistry.add`.

Avaliacao:

1. Filtra por ``source`` (regra com ``source == "*"`` aplica-se a todas).
2. Filtra por ``enabled`` (desativadas sao ignoradas).
3. Testa ``condition_key`` no ``AlertEvent.data`` com ``operator``.
4. Retorna a primeira regra correspondente (ordenada por ``priority``).

Operadores suportados: ``eq``, ``ne``, ``gt``, ``gte``, ``lt``, ``lte``,
``contains``, ``regex``, ``in``, ``exists``.

Uso:

    registry = RuleRegistry(default_rules())
    rule = registry.evaluate(event)
    if rule:
        engine.create_alert(event, rule)
"""

from __future__ import annotations

import re

from app.core.alerts.models import (
    AlertRule,
    AlertSource,
    Severity,
)

__all__ = [
    "OPERATORS",
    "RuleRegistry",
    "default_rules",
    "evaluate_condition",
]


def _safe_compare(actual: object, operator: str, expected: object) -> bool:
    """Comparar dois valores com seguranca de tipo.

    Para operadores numericos (``gt``, ``gte``, ``lt``, ``lte``),
    tenta converter ambos para ``float`` antes da comparacao. Se
    a conversao falhar, retorna ``False`` (defensivo, sem excecao).

    Args:
        actual: Valor real extraido do evento.
        operator: Operador de comparacao.
        expected: Valor esperado definido na regra.

    Returns:
        ``True`` se a condicao e satisfeita, ``False`` caso contrario.
    """
    if operator == "eq":
        return actual == expected
    if operator == "ne":
        return actual != expected
    if operator == "exists":
        # ``expected`` booleano: True = deve existir, False = nao deve
        should_exist = bool(expected)
        exists = actual is not None
        return exists if should_exist else not exists
    if operator == "in":
        # expected deve ser uma colecao (list, tuple, set, frozenset)
        if not isinstance(expected, (list, tuple, set, frozenset)):
            return False
        return actual in expected
    if operator == "contains":
        # ``actual`` deve conter ``expected`` (string/list)
        try:
            return expected in actual  # type: ignore[operator]
        except TypeError:
            return False
    if operator == "regex":
        # ``expected`` e o padrao regex; ``actual`` e o texto
        if not isinstance(actual, str) or not isinstance(expected, str):
            return False
        try:
            return re.search(expected, actual) is not None
        except re.error:
            return False
    # Operadores numericos
    if operator in ("gt", "gte", "lt", "lte"):
        try:
            a = float(actual)  # type: ignore[arg-type]
            e = float(expected)  # type: ignore[arg-type]
        except (ValueError, TypeError):
            return False
        if operator == "gt":
            return a > e
        if operator == "gte":
            return a >= e
        if operator == "lt":
            return a < e
        return a <= e
    # Operador desconhecido
    return False


def evaluate_condition(rule: AlertRule, event_data: dict[str, object]) -> bool:
    """Avaliar se um evento satisfaz a condicao de uma regra.

    Extrai ``event_data[condition_key]`` e compara com
    ``rule.condition_value`` usando ``rule.operator``.

    Args:
        rule: Regra a avaliar.
        event_data: Metadados do evento (``AlertEvent.data``).

    Returns:
        ``True`` se a condicao e satisfeita, ``False`` caso contrario
        ou se a chave nao existir (exceto para operador ``"exists"``).
    """
    key = rule.condition_key
    has_key = key in event_data
    actual = event_data.get(key) if has_key else None

    # Operador "exists" e o unico onde None e valido
    if rule.operator == "exists":
        return _safe_compare(actual, "exists", rule.condition_value)

    # Para outros operadores, se a chave nao existe, condicao e False
    if not has_key or actual is None:
        return False

    return _safe_compare(actual, rule.operator, rule.condition_value)


#: Operadores suportados (documentacao e validacao).
OPERATORS: frozenset[str] = frozenset(
    {"eq", "ne", "gt", "gte", "lt", "lte", "contains", "regex", "in", "exists"}
)


class RuleRegistry:
    """Repositorio de regras de alerta com avaliacao.

    Attributes:
        rules: Lista de regras registradas.
    """

    def __init__(self, rules: list[AlertRule] | None = None) -> None:
        self._rules: list[AlertRule] = list(rules) if rules else []

    def add(self, rule: AlertRule) -> None:
        """Adicionar uma regra ao repositorio.

        Args:
            rule: Regra a adicionar.

        Raises:
            ValueError: Se ``rule.rule_id`` ja existe no repositorio.
        """
        if any(r.rule_id == rule.rule_id for r in self._rules):
            raise ValueError(f"Regra com rule_id '{rule.rule_id}' ja existe")
        self._rules.append(rule)

    def remove(self, rule_id: str) -> bool:
        """Remover uma regra do repositorio.

        Args:
            rule_id: ID da regra a remover.

        Returns:
            ``True`` se removida, ``False`` se nao encontrada.
        """
        for i, rule in enumerate(self._rules):
            if rule.rule_id == rule_id:
                self._rules.pop(i)
                return True
        return False

    def get(self, rule_id: str) -> AlertRule | None:
        """Consultar regra por ID.

        Args:
            rule_id: ID da regra.

        Returns:
            :class:`AlertRule` se encontrada, ``None`` caso contrario.
        """
        for rule in self._rules:
            if rule.rule_id == rule_id:
                return rule
        return None

    def list_rules(self) -> list[AlertRule]:
        """Retornar todas as regras (copia defensiva)."""
        return list(self._rules)

    def __len__(self) -> int:
        return len(self._rules)

    def evaluate(
        self,
        source: str,
        event_type: str,  # noqa: ARG002
        data: dict[str, object],
    ) -> AlertRule | None:
        """Avaliar um evento e retornar a primeira regra correspondente.

        Itera as regras ordenadas por ``priority`` (ascendente), filtrando
        por ``source`` (``"*"`` = todas) e ``enabled``.

        Args:
            source: Origem do evento.
            event_type: Tipo do evento (nao usado no match, mas disponivel).
            data: Metadados do evento para avaliacao da condicao.

        Returns:
            :class:`AlertRule` correspondente, ou ``None`` se nenhuma regra
            corresponder.
        """
        # Ordenar por priority (estavel: preserva ordem de registro em empate)
        sorted_rules = sorted(enumerate(self._rules), key=lambda x: (x[1].priority, x[0]))
        for _, rule in sorted_rules:
            if not rule.enabled:
                continue
            # Filtra por source (* = todas)
            if rule.source != "*" and rule.source != source:
                continue
            if evaluate_condition(rule, data):
                return rule
        return None


def default_rules() -> list[AlertRule]:
    """Retornar regras embutidas padrao do EDY Shield.

    Cobre os analisadores existentes (String, Entropy) e o FIM:

    * ``FIM_MODIFIED`` -- arquivo modificado -> HIGH
    * ``FIM_CREATED`` -- arquivo criado -> MEDIUM
    * ``FIM_DELETED`` -- arquivo deletado -> CRITICAL
    * ``STRING_SECRET`` -- achado de string em categoria ``secret`` -> CRITICAL
    * ``STRING_URL`` -- achado de string em categoria ``url`` -> LOW
    * ``ENTROPY_HIGH`` -- entropia alta (>6.0 bits) -> HIGH
    * ``ENTROPY_MEDIUM`` -- entropia media (>=4.5) -> MEDIUM
    * ``DEFAULT_CATCH_ALL`` -- fallback para qualquer evento -> INFO

    Returns:
        Lista de :class:`AlertRule` embarcadas.
    """
    return [
        # FIM: mudancas de arquivo
        AlertRule(
            rule_id="FIM_MODIFIED",
            name="Arquivo modificado",
            source=AlertSource.FIM,
            condition_key="event_type",
            operator="eq",
            condition_value="file_modified",
            target_severity=Severity.HIGH,
            title_template="Arquivo modificado: {target}",
            description_template="O arquivo {target} foi modificado.",
            priority=10,
            suppression_window_seconds=300,
        ),
        AlertRule(
            rule_id="FIM_CREATED",
            name="Arquivo criado",
            source=AlertSource.FIM,
            condition_key="event_type",
            operator="eq",
            condition_value="file_created",
            target_severity=Severity.MEDIUM,
            title_template="Arquivo criado: {target}",
            description_template="Novo arquivo detectado: {target}.",
            priority=10,
            suppression_window_seconds=300,
        ),
        AlertRule(
            rule_id="FIM_DELETED",
            name="Arquivo deletado",
            source=AlertSource.FIM,
            condition_key="event_type",
            operator="eq",
            condition_value="file_deleted",
            target_severity=Severity.CRITICAL,
            title_template="Arquivo deletado: {target}",
            description_template="Arquivo removido: {target}.",
            priority=10,
            suppression_window_seconds=300,
        ),
        # String Analyzer
        AlertRule(
            rule_id="STRING_SECRET",
            name="Secredo/trecho sensivel detectado",
            source=AlertSource.STRING_ANALYZER,
            condition_key="category",
            operator="eq",
            condition_value="secret",
            target_severity=Severity.CRITICAL,
            title_template="Secredo potencial em {target}",
            description_template="Analisador de strings encontrou um segredo em {target}.",
            priority=20,
            suppression_window_seconds=600,
        ),
        AlertRule(
            rule_id="STRING_URL",
            name="URL detectada",
            source=AlertSource.STRING_ANALYZER,
            condition_key="category",
            operator="eq",
            condition_value="url",
            target_severity=Severity.LOW,
            title_template="URL encontrada em {target}",
            description_template="Analisador de strings detectou URL em {target}.",
            priority=30,
            suppression_window_seconds=300,
        ),
        # Entropy Analyzer
        AlertRule(
            rule_id="ENTROPY_HIGH",
            name="Entropia alta detectada",
            source=AlertSource.ENTROPY_ANALYZER,
            condition_key="entropy",
            operator="gte",
            condition_value=6.0,
            target_severity=Severity.HIGH,
            title_template="Entropia alta em {target}",
            description_template="Arquivo {target} apresenta entropia >= 6.0 bits (possivel conteudo ofuscado/criptografado).",
            priority=20,
            suppression_window_seconds=300,
        ),
        AlertRule(
            rule_id="ENTROPY_MEDIUM",
            name="Entropia media detectada",
            source=AlertSource.ENTROPY_ANALYZER,
            condition_key="entropy",
            operator="gte",
            condition_value=4.5,
            target_severity=Severity.MEDIUM,
            title_template="Entropia media em {target}",
            description_template="Arquivo {target} apresenta entropia >= 4.5 bits.",
            priority=30,
            suppression_window_seconds=300,
        ),
        # Catch-all (fallback)
        AlertRule(
            rule_id="DEFAULT_CATCH_ALL",
            name="Alerta generico",
            source="*",
            condition_key="event_type",
            operator="exists",
            condition_value=True,
            target_severity=Severity.INFO,
            title_template="Evento registrado: {event_type}",
            description_template="Evento de origem {source} no alvo {target}.",
            priority=999,
            suppression_window_seconds=300,
        ),
    ]
