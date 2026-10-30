# despachante-digital/tests/test_agrupamento.py
"""Testes da Etapa 3: as divergências detectadas batem com o gabarito."""

from dataclasses import replace

from despachante.agrupamento import analisar
from despachante.extracao import PdfIlegivelError, extrair_documento


def _extrair_lote(pasta):
    docs, erros = [], {}
    for pdf in sorted(pasta.glob("*.pdf")):
        try:
            docs.append(extrair_documento(pdf))
        except PdfIlegivelError as e:
            erros[pdf.name] = {"motivo": str(e)}
    return docs, erros


def _rotulo(d) -> str:
    """Converte a divergência para o formato usado no gabarito."""
    if d.tipo == "campo_ausente":
        return "campo_ausente:" + d.detalhe.split()[0]
    if d.tipo == "documento_ausente":
        return "documento_ausente:" + d.detalhe.split()[0]
    if d.tipo == "documento_ilegivel":
        return "documento_ilegivel:" + d.detalhe.split()[-2]
    return d.tipo


def test_divergencias_iguais_ao_gabarito(lote_sintetico):
    pasta, cenarios = lote_sintetico
    processos = analisar(*_extrair_lote(pasta))
    assert list(processos) == [c["processo"] for c in cenarios]
    for cen in cenarios:
        proc = processos[cen["processo"]]
        assert sorted(_rotulo(d) for d in proc.divergencias) == \
            sorted(cen["divergencias_esperadas"]), cen["processo"]


def test_tolerancia_absorve_arredondamento(lote_sintetico):
    pasta, _ = lote_sintetico
    docs, _ = _extrair_lote(pasta)
    nf = next(d for d in docs if d.arquivo == "PROC-2026-001_NF.pdf")
    fat = next(d for d in docs if d.arquivo == "PROC-2026-001_FATURA.pdf")
    nf_ajustada = replace(nf, peso_total_kg=nf.peso_total_kg + 0.3)  # dentro de 0,5 kg
    proc = analisar([nf_ajustada, fat])["PROC-2026-001"]
    assert proc.status == "CONFORME"


def test_ncm_diferente_vira_divergencia(lote_sintetico):
    pasta, _ = lote_sintetico
    docs, _ = _extrair_lote(pasta)
    nf = next(d for d in docs if d.arquivo == "PROC-2026-001_NF.pdf")
    fat = next(d for d in docs if d.arquivo == "PROC-2026-001_FATURA.pdf")
    proc = analisar([replace(nf, ncms=["9999.99.99"]), fat])["PROC-2026-001"]
    assert [d.tipo for d in proc.divergencias] == ["ncm"]
