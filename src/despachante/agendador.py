# despachante-digital/src/despachante/agendador.py
"""Agendamento do relatório com APScheduler (Etapa 6).

O monitor roda o tempo todo; o relatório sai no horário do CRON_RELATORIO
(padrão: 18h, segunda a sexta).
"""

from __future__ import annotations

import logging

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from despachante.config import Config
from despachante.pipeline import gerar_saidas
from despachante.registro import Registro

log = logging.getLogger(__name__)


def _tarefa_relatorio(config: Config, registro: Registro) -> None:
    # Uma exceção aqui não pode derrubar o agendador: registra e espera o próximo.
    try:
        gerar_saidas(config, registro)
    except Exception:
        log.exception("relatorio_agendado_falhou")


def criar_agendador(config: Config, registro: Registro) -> BackgroundScheduler:
    agendador = BackgroundScheduler(timezone="America/Sao_Paulo")
    agendador.add_job(
        _tarefa_relatorio,
        CronTrigger.from_crontab(config.cron_relatorio, timezone="America/Sao_Paulo"),
        args=[config, registro],
        id="relatorio_diario",
        coalesce=True,            # se o PC estava desligado, roda uma vez só, não várias
        misfire_grace_time=3600,  # aceita atraso de até 1 h
        max_instances=1,
    )
    return agendador
