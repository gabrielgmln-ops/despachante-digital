# despachante-digital/tests/test_monitor.py
"""Testes da Etapa 2: processamento de arquivos e monitor de pasta."""

import shutil
import time
from dataclasses import replace
from pathlib import Path

import pytest

from despachante.config import Config
from despachante.monitor import iniciar_monitor, processar_pendentes
from despachante.registro import Registro


@pytest.fixture
def ambiente(tmp_path) -> tuple[Config, Registro]:
    config = replace(
        Config(),
        pasta_entrada=tmp_path / "entrada",
        pasta_processados=tmp_path / "processados",
        pasta_erros=tmp_path / "erros",
        pasta_saida=tmp_path / "saida",
        pasta_logs=tmp_path / "logs",
    )
    config.criar_pastas()
    return config, Registro(config.arquivo_registro)


def _copiar_lote(origem: Path, destino: Path) -> None:
    for pdf in origem.glob("*.pdf"):
        shutil.copy(pdf, destino)


def test_lote_inteiro_nao_para_no_pdf_corrompido(ambiente, lote_sintetico):
    config, registro = ambiente
    _copiar_lote(lote_sintetico[0], config.pasta_entrada)

    assert processar_pendentes(config, registro) == 15
    assert len(registro.documentos()) == 14
    assert list(registro.erros()) == ["PROC-2026-007_NF.pdf"]
    assert len(list(config.pasta_processados.glob("*.pdf"))) == 14
    assert [p.name for p in config.pasta_erros.glob("*.pdf")] == ["PROC-2026-007_NF.pdf"]
    assert not list(config.pasta_entrada.glob("*.pdf"))


def test_monitor_pega_arquivo_novo(ambiente, lote_sintetico):
    config, registro = ambiente
    observador = iniciar_monitor(config, registro)
    try:
        shutil.copy(lote_sintetico[0] / "PROC-2026-001_NF.pdf", config.pasta_entrada)
        limite = time.time() + 15
        while time.time() < limite and not registro.documentos():
            time.sleep(0.2)
    finally:
        observador.stop()
        observador.join()
    docs = registro.documentos()
    assert [d.arquivo for d in docs] == ["PROC-2026-001_NF.pdf"]
    assert (config.pasta_processados / "PROC-2026-001_NF.pdf").exists()


def test_arquivo_nao_pdf_e_ignorado(ambiente):
    config, registro = ambiente
    (config.pasta_entrada / "leia-me.txt").write_text("nada")
    assert processar_pendentes(config, registro) == 0
    assert (config.pasta_entrada / "leia-me.txt").exists()
