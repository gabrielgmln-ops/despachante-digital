# despachante-digital/tests/test_gerador.py
"""Testes da Etapa 0: o gerador cria os PDFs esperados e o texto é extraível."""

import json
import subprocess
import sys
from pathlib import Path

import pdfplumber
import pytest

RAIZ = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def lote(tmp_path_factory) -> tuple[Path, list[dict]]:
    pasta = tmp_path_factory.mktemp("entrada")
    gabarito = pasta.parent / "gabarito.json"
    subprocess.run(
        [sys.executable, str(RAIZ / "scripts" / "gerar_pdfs.py"),
         "--saida", str(pasta), "--gabarito", str(gabarito)],
        check=True, capture_output=True,
    )
    return pasta, json.loads(gabarito.read_text(encoding="utf-8"))


def test_gera_15_pdfs_para_8_processos(lote):
    pasta, cenarios = lote
    assert len(cenarios) == 8
    assert len(list(pasta.glob("*.pdf"))) == 15  # PROC-005 não tem fatura


def test_pdfs_legiveis_tem_texto(lote):
    pasta, cenarios = lote
    for cen in cenarios:
        for doc in cen["documentos"]:
            if not doc["legivel"]:
                continue
            with pdfplumber.open(pasta / doc["arquivo"]) as pdf:
                texto = pdf.pages[0].extract_text()
            assert doc["numero"] in texto
            assert cen["processo"] in texto


def test_pdf_corrompido_falha_ao_abrir(lote):
    pasta, _ = lote
    with pytest.raises(Exception):
        with pdfplumber.open(pasta / "PROC-2026-007_NF.pdf") as pdf:
            pdf.pages[0].extract_text()


def test_gerador_e_deterministico(lote, tmp_path):
    _, cenarios = lote
    gab2 = tmp_path / "g2.json"
    subprocess.run(
        [sys.executable, str(RAIZ / "scripts" / "gerar_pdfs.py"),
         "--saida", str(tmp_path / "e2"), "--gabarito", str(gab2)],
        check=True, capture_output=True,
    )
    assert json.loads(gab2.read_text(encoding="utf-8")) == cenarios
