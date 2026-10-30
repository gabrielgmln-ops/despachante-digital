# despachante-digital/tests/test_ponta_a_ponta.py
"""Testes da Etapa 6: logs JSON, agendador e o fluxo completo do lote."""

import json
import logging
import shutil
from dataclasses import replace

import pandas as pd

from despachante.agendador import criar_agendador
from despachante.config import Config
from despachante.logs import configurar_logs
from despachante.pipeline import executar_lote
from despachante.registro import Registro


def _config(tmp_path) -> Config:
    return replace(Config(), pasta_entrada=tmp_path / "entrada",
                   pasta_processados=tmp_path / "processados", pasta_erros=tmp_path / "erros",
                   pasta_saida=tmp_path / "saida", pasta_logs=tmp_path / "logs")


def test_lote_completo_gera_planilha_e_relatorio(lote_sintetico, tmp_path):
    config = _config(tmp_path)
    config.criar_pastas()
    for pdf in lote_sintetico[0].glob("*.pdf"):
        shutil.copy(pdf, config.pasta_entrada)

    r = executar_lote(config, Registro(config.arquivo_registro), enviar_email=False)

    assert r.resumo == {"total": 8, "conformes": 3, "divergentes": 5,
                        "divergencias": 5, "erros": 1}
    assert r.planilha.exists() and r.relatorio.exists()
    assert len(pd.read_excel(r.planilha, sheet_name="Processos")) == 8
    assert r.email_enviado is False


def test_logs_sao_json_com_campos_extras(tmp_path):
    configurar_logs(tmp_path)
    logging.getLogger("teste").warning("campos_ausentes", extra={"arquivo": "x.pdf"})
    for h in logging.getLogger().handlers:
        h.flush()
    linha = (tmp_path / "despachante.log").read_text(encoding="utf-8").strip().splitlines()[-1]
    evento = json.loads(linha)
    assert evento["evento"] == "campos_ausentes"
    assert evento["arquivo"] == "x.pdf"
    assert evento["nivel"] == "WARNING"
    for h in list(logging.getLogger().handlers):  # libera o arquivo no Windows
        h.close()
        logging.getLogger().removeHandler(h)


def test_agendador_usa_cron_da_config(tmp_path):
    config = replace(_config(tmp_path), cron_relatorio="30 7 * * *")
    agendador = criar_agendador(config, Registro(config.arquivo_registro))
    agendador.start(paused=True)
    try:
        proximo = agendador.get_job("relatorio_diario").next_run_time
        assert (proximo.hour, proximo.minute) == (7, 30)
    finally:
        agendador.shutdown(wait=False)
