# despachante-digital/src/despachante/pipeline.py
"""Orquestração: do registro de documentos até planilha, relatório e e-mail."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from despachante.agrupamento import analisar
from despachante.config import Config
from despachante.email_envio import enviar_relatorio
from despachante.monitor import processar_pendentes
from despachante.planilha import gerar_planilha
from despachante.registro import Registro
from despachante.relatorio import renderizar_relatorio, resumir, salvar_relatorio

log = logging.getLogger(__name__)


@dataclass
class ResultadoRelatorio:
    planilha: Path
    relatorio: Path
    resumo: dict
    email_enviado: bool


def gerar_saidas(config: Config, registro: Registro, enviar_email: bool = True,
                 agora: datetime | None = None) -> ResultadoRelatorio:
    """Lê o registro, consolida e (opcionalmente) envia por e-mail."""
    agora = agora or datetime.now()
    carimbo = agora.strftime("%Y%m%d_%H%M%S")
    erros = registro.erros()
    processos = analisar(registro.documentos(), erros,
                         config.tolerancia_valor_usd, config.tolerancia_peso_kg)

    planilha = gerar_planilha(processos, erros, config.pasta_saida / f"consolidado_{carimbo}.xlsx")
    html = renderizar_relatorio(processos, erros, agora)
    relatorio = salvar_relatorio(html, config.pasta_saida / f"relatorio_{carimbo}.html")
    resumo = resumir(processos, erros)
    log.info("saidas_geradas", extra={"planilha": str(planilha), "relatorio": str(relatorio),
                                      **resumo})

    enviado = False
    if enviar_email:
        assunto = (f"[Despachante Digital] {resumo['divergentes']} processo(s) divergente(s) "
                   f"de {resumo['total']} - {agora:%d/%m/%Y}")
        enviado = enviar_relatorio(config, assunto, html, [planilha])
    return ResultadoRelatorio(planilha, relatorio, resumo, enviado)


def executar_lote(config: Config, registro: Registro,
                  enviar_email: bool = True) -> ResultadoRelatorio:
    """Modo lote: processa o que está na entrada agora e gera as saídas."""
    config.criar_pastas()
    qtd = processar_pendentes(config, registro)
    log.info("lote_processado", extra={"arquivos": qtd})
    return gerar_saidas(config, registro, enviar_email)
