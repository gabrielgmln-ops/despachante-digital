# despachante-digital/tests/test_planilha.py
"""Testes da Etapa 4: a planilha tem as abas e as linhas certas."""

import pandas as pd

from despachante.agrupamento import analisar
from despachante.extracao import PdfIlegivelError, extrair_documento
from despachante.planilha import gerar_planilha


def test_planilha_consolidada(lote_sintetico, tmp_path):
    pasta, cenarios = lote_sintetico
    docs, erros = [], {}
    for pdf in sorted(pasta.glob("*.pdf")):
        try:
            docs.append(extrair_documento(pdf))
        except PdfIlegivelError as e:
            erros[pdf.name] = {"motivo": str(e), "quando": "agora"}

    destino = gerar_planilha(analisar(docs, erros), erros, tmp_path / "consolidado.xlsx")
    abas = pd.read_excel(destino, sheet_name=None)

    assert set(abas) == {"Processos", "Documentos", "Divergencias", "Erros"}
    assert len(abas["Processos"]) == 8
    assert len(abas["Documentos"]) == 14
    assert len(abas["Erros"]) == 1
    esperadas = sum(len(c["divergencias_esperadas"]) for c in cenarios)
    assert len(abas["Divergencias"]) == esperadas
    status = dict(zip(abas["Processos"]["Processo"], abas["Processos"]["Status"]))
    assert status["PROC-2026-001"] == "CONFORME"
    assert status["PROC-2026-003"] == "DIVERGENTE"
