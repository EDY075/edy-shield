"""Canais internos de saida de alertas (EDY Shield -- M3-T04).

Os canais sao o mecanismo de **dispatch** do
:class:`~app.core.alerts.engine.AlertEngine`: toda vez que um alerta e
criado ou atualizado, o engine notifica os canais registrados.

Canais disponiveis:

* :class:`ConsoleChannel` -- loga no console via ``logging``.
* :class:`FileChannel` -- escreve em arquivo de log dedicado.
* :class:`CompositeChannel` -- combina multiplos canais.
* :class:`NullChannel` -- canal nulo (para testes).

Todos herdam de :class:`BaseAlertChannel` e usam apenas stdlib
(ADR-009). Canais externos (E-mail, Slack, Discord, Webhook) estao
FORA do escopo da M3 e serao adicionados em versoes futuras.

Uso:

    engine = AlertEngine(
        channels=[ConsoleChannel(), FileChannel(path="alerts.log")]
    )
"""

from __future__ import annotations

import logging
import os
from abc import ABC, abstractmethod
from datetime import UTC, datetime

from app.core.alerts.models import AlertRecord

__all__ = [
    "BaseAlertChannel",
    "CompositeChannel",
    "ConsoleChannel",
    "FileChannel",
    "NullChannel",
]


def _format_alert(record: AlertRecord) -> str:
    """Formatar alerta para saida textual (log/arquivo).

    Formato:
        ``[TIMESTAMP] SEVERITY [source] title (id: alert_id, count: N)``
    """
    ts = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S")
    return (
        f"[{ts}] {record.severity.value:>8} "
        f"[{record.source}] {record.title} "
        f"(id: {record.alert_id}, count: {record.count})"
    )


class BaseAlertChannel(ABC):
    """Classe base abstrata para todos os canais de alerta.

    Subclasses devem implementar :meth:`send` para definir o
    comportamento de saida.
    """

    @abstractmethod
    def send(self, record: AlertRecord, is_update: bool = False) -> None:
        """Enviar alerta para o canal.

        Args:
            record: Alerta a ser enviado.
            is_update: ``True`` se o alerta ja existia e foi atualizado
                (dedup incrementou count), ``False`` se e um novo alerta.
        """
        ...


class ConsoleChannel(BaseAlertChannel):
    """Canal de saida para console via ``logging``.

    Usa o logger ``edyshield.alerts`` no nivel ``INFO``. Configuravel
    por nome de logger.

    Attributes:
        logger_name: Nome do logger (default ``"edyshield.alerts"``).
    """

    def __init__(self, logger_name: str = "edyshield.alerts") -> None:
        self._logger = logging.getLogger(logger_name)
        self._label = "ALERTA NOVO" if logger_name == "edyshield.alerts" else "UPDATE"

    def send(self, record: AlertRecord, is_update: bool = False) -> None:
        label = "ALERTA ATUALIZADO" if is_update else "ALERTA NOVO"
        self._logger.info("[%s] %s", label, _format_alert(record))


class FileChannel(BaseAlertChannel):
    """Canal de saida para arquivo de log dedicado.

    Escreve alertas em formato texto simples em um arquivo de log.
    Cria o diretorio pai automaticamente se nao existir.
    Usa codificacao UTF-8.

    Attributes:
        path: Caminho do arquivo de log.
    """

    def __init__(self, path: str | os.PathLike[str] = "alerts.log") -> None:
        self._path = os.fspath(path)
        # Garantir que o diretorio pai existe
        parent = os.path.dirname(self._path)
        if parent:
            os.makedirs(parent, exist_ok=True)

    @property
    def path(self) -> str:
        """Caminho do arquivo de log."""
        return self._path

    def send(self, record: AlertRecord, is_update: bool = False) -> None:
        try:
            with open(self._path, "a", encoding="utf-8") as f:
                label = "UPDATE" if is_update else "NEW"
                f.write(f"[{label}] {_format_alert(record)}\n")
        except OSError:
            # Falha de I/O nao deve interromper o engine
            logger = logging.getLogger("edyshield.alerts.file")
            logger.warning("Falha ao escrever alerta no arquivo %s", self._path)


class CompositeChannel(BaseAlertChannel):
    """Combina multiplos canais em um so.

    Delega a chamada :meth:`send` para todos os canais internos,
    em ordem de registro.

    Attributes:
        channels: Lista de canais filhos.
    """

    def __init__(self, channels: list[BaseAlertChannel] | None = None) -> None:
        self._channels: list[BaseAlertChannel] = channels or []

    def add(self, channel: BaseAlertChannel) -> None:
        """Adicionar um canal filho."""
        self._channels.append(channel)

    def send(self, record: AlertRecord, is_update: bool = False) -> None:
        for channel in self._channels:
            channel.send(record, is_update=is_update)


class NullChannel(BaseAlertChannel):
    """Canal nulo: nao faz nada (usado em testes).

    Todas as chamadas sao ignoradas silenciosamente.
    """

    def send(self, record: AlertRecord, is_update: bool = False) -> None:
        pass
