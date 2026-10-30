# despachante-digital/src/despachante/agrupamento.py
"""Agrupamento por processo e detecção de divergências (Etapa 3).

Regras de divergência de um processo:
  - documento_ausente  : falta NF ou fatura comercial
  - documento_ilegivel : o PDF de um dos tipos foi para a pasta de erros
  - campo_ausente      : um documento não trouxe um campo obrigatório
  - valor              : |valor NF - valor fatura| > tolerância (USD)
  - peso               : |peso NF - peso fatura|  > tolerância (kg)
  - ncm                : os conjuntos de NCM diferem entre NF e fatura
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from despachante.extracao import DocumentoExtraido

TIPOS = ("nota_fiscal", "fatura_comercial")

# Nome de arquivo do tipo "PROC-2026-007_NF.pdf": usado para saber a que
# processo pertence um PDF ilegível, já que dele não se extrai nada.
PADRAO_ARQUIVO = re.compile(r"^(?P<processo>.+?)_(?P<sufixo>NF|FATURA)", re.IGNORECASE)
SUFIXO_TIPO = {"NF": "nota_fiscal", "FATURA": "fatura_comercial"}


@dataclass
class Divergencia:
    processo: str
    tipo: str          # valor | peso | ncm | campo_ausente | documento_ausente | documento_ilegivel
    detalhe: str
    valor_nf: float | str | None = None
    valor_fatura: float | str | None = None
    diferenca: float | None = None


@dataclass
class Processo:
    numero: str
    documentos: dict[str, DocumentoExtraido] = field(default_factory=dict)
    ilegiveis: list[str] = field(default_factory=list)   # tipos cujo PDF falhou
    divergencias: list[Divergencia] = field(default_factory=list)

    @property
    def nf(self) -> DocumentoExtraido | None:
        return self.documentos.get("nota_fiscal")

    @property
    def fatura(self) -> DocumentoExtraido | None:
        return self.documentos.get("fatura_comercial")

    @property
    def status(self) -> str:
        return "CONFORME" if not self.divergencias else "DIVERGENTE"


def agrupar(documentos: list[DocumentoExtraido],
            erros: dict[str, dict] | None = None) -> dict[str, Processo]:
    """Junta os documentos pelo número do processo."""
    processos: dict[str, Processo] = {}
    for doc in documentos:
        chave = doc.processo or f"SEM-PROCESSO:{doc.arquivo}"
        proc = processos.setdefault(chave, Processo(chave))
        proc.documentos[doc.tipo] = doc
    for arquivo in (erros or {}):
        achado = PADRAO_ARQUIVO.match(arquivo)
        chave = achado["processo"] if achado else f"DESCONHECIDO:{arquivo}"
        tipo = SUFIXO_TIPO[achado["sufixo"].upper()] if achado else "desconhecido"
        processos.setdefault(chave, Processo(chave)).ilegiveis.append(tipo)
    return dict(sorted(processos.items()))


def _comparar_numero(proc: Processo, campo: str, rotulo: str, tolerancia: float) -> None:
    v_nf = getattr(proc.nf, campo)
    v_fat = getattr(proc.fatura, campo)
    if v_nf is None or v_fat is None:
        return  # já reportado como campo_ausente
    diferenca = round(v_nf - v_fat, 3)
    if abs(diferenca) > tolerancia:
        proc.divergencias.append(Divergencia(
            proc.numero, rotulo,
            f"{rotulo} da NF difere da fatura em {diferenca:+,.3f}",
            v_nf, v_fat, diferenca))


def detectar_divergencias(proc: Processo, tolerancia_valor: float = 0.01,
                          tolerancia_peso: float = 0.5) -> list[Divergencia]:
    proc.divergencias = []
    for tipo in proc.ilegiveis:
        proc.divergencias.append(Divergencia(proc.numero, "documento_ilegivel",
                                             f"PDF de {tipo} ilegível"))
    for tipo in TIPOS:
        if tipo not in proc.documentos and tipo not in proc.ilegiveis:
            proc.divergencias.append(Divergencia(proc.numero, "documento_ausente",
                                                 f"{tipo} não recebida"))
    for doc in proc.documentos.values():
        for campo in doc.campos_ausentes:
            proc.divergencias.append(Divergencia(proc.numero, "campo_ausente",
                                                 f"{campo} ausente em {doc.tipo} ({doc.arquivo})"))

    if proc.nf and proc.fatura:
        _comparar_numero(proc, "valor_total_usd", "valor", tolerancia_valor)
        _comparar_numero(proc, "peso_total_kg", "peso", tolerancia_peso)
        if proc.nf.ncms and proc.fatura.ncms and set(proc.nf.ncms) != set(proc.fatura.ncms):
            proc.divergencias.append(Divergencia(
                proc.numero, "ncm", "NCMs diferentes entre NF e fatura",
                ", ".join(proc.nf.ncms), ", ".join(proc.fatura.ncms)))
    return proc.divergencias


def analisar(documentos: list[DocumentoExtraido], erros: dict[str, dict] | None = None,
             tolerancia_valor: float = 0.01, tolerancia_peso: float = 0.5) -> dict[str, Processo]:
    """Atalho: agrupa e detecta divergências de todos os processos."""
    processos = agrupar(documentos, erros)
    for proc in processos.values():
        detectar_divergencias(proc, tolerancia_valor, tolerancia_peso)
    return processos
