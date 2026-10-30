# despachante-digital/tests/test_extracao.py
"""Testes da Etapa 1: extração comparada com o gabarito do gerador."""

import pytest

from despachante.extracao import (
    PdfIlegivelError,
    extrair_documento,
    numero_br,
    numero_us,
)


def test_conversao_de_numeros():
    assert numero_br("1.250,500") == 1250.5
    assert numero_us("1,250.500") == 1250.5
    assert numero_br("12,30") == 12.3


def test_extrai_todos_os_pdfs_legiveis_igual_ao_gabarito(lote_sintetico, documentos_gabarito):
    pasta, _ = lote_sintetico
    for nome, esperado in documentos_gabarito.items():
        if not esperado["legivel"]:
            continue
        doc = extrair_documento(pasta / nome)
        assert doc.tipo == esperado["tipo"], nome
        assert doc.processo == esperado["processo"], nome
        assert doc.numero == esperado["numero"], nome
        assert doc.data == esperado["data"], nome
        assert doc.valor_total_usd == pytest.approx(esperado["valor_total_usd"]), nome
        if esperado["peso_total_kg"] is None:
            assert doc.peso_total_kg is None
        else:
            assert doc.peso_total_kg == pytest.approx(esperado["peso_total_kg"]), nome
        assert doc.ncms == esperado["ncms"], nome


def test_campo_ausente_nao_levanta_erro(lote_sintetico):
    pasta, _ = lote_sintetico
    doc = extrair_documento(pasta / "PROC-2026-006_NF.pdf")
    assert doc.campos_ausentes == ["peso_total_kg"]
    assert doc.valor_total_usd is not None


def test_pdf_corrompido_levanta_ilegivel(lote_sintetico):
    pasta, _ = lote_sintetico
    with pytest.raises(PdfIlegivelError):
        extrair_documento(pasta / "PROC-2026-007_NF.pdf")


def test_arquivo_inexistente_levanta_ilegivel(tmp_path):
    with pytest.raises(PdfIlegivelError):
        extrair_documento(tmp_path / "nao_existe.pdf")
