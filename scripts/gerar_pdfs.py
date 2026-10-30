# despachante-digital/scripts/gerar_pdfs.py
"""Gerador de PDFs sintéticos de importação (Etapa 0).

Para cada processo de importação gera até dois documentos:
  - Nota Fiscal de Importação (formato brasileiro: 1.234,56 e dd/mm/aaaa)
  - Commercial Invoice / fatura comercial (formato americano: 1,234.56 e aaaa-mm-dd)

Os cenários incluem casos felizes e casos de erro de propósito, para que as
etapas seguintes tenham o que detectar. Ao final grava `gabarito.json` com os
valores esperados de cada documento e as divergências esperadas por processo.

Todos os dados são fictícios. Uso:
    python scripts/gerar_pdfs.py                 # gera em dados/entrada
    python scripts/gerar_pdfs.py --saida outra   # gera em outra pasta
"""

from __future__ import annotations

import argparse
import json
import random
from dataclasses import asdict, dataclass, field
from datetime import date, timedelta
from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

# Semente fixa: rodar duas vezes gera exatamente os mesmos documentos.
SEMENTE = 2026

# Catálogo fictício de mercadorias (descrição, NCM, peso unitário kg, preço unitário USD).
CATALOGO = [
    ("Notebook 14 polegadas", "8471.30.12", 1.600, 412.50),
    ("Monitor LED 24 polegadas", "8528.52.20", 3.900, 98.40),
    ("Teclado mecanico USB", "8471.60.52", 0.850, 21.75),
    ("Roteador wireless", "8517.62.77", 0.420, 33.10),
    ("Cabo HDMI 2m", "8544.42.00", 0.120, 2.35),
    ("Fone de ouvido bluetooth", "8518.30.00", 0.250, 14.90),
]

IMPORTADOR = "Comercial Exemplo Importadora Ltda (CNPJ 00.000.000/0001-00)"
EXPORTADOR = "Sample Electronics Co., Ltd. - Shenzhen, CN"


@dataclass
class Item:
    descricao: str
    ncm: str
    quantidade: int
    peso_kg: float       # peso líquido total do item
    valor_usd: float     # valor FOB total do item


@dataclass
class Documento:
    """O que foi impresso no PDF (e, portanto, o que a extração deve achar)."""
    arquivo: str
    tipo: str            # "nota_fiscal" | "fatura_comercial"
    processo: str
    numero: str | None
    data: str | None     # sempre ISO no gabarito, independente do formato impresso
    valor_total_usd: float | None
    peso_total_kg: float | None
    ncms: list[str]
    legivel: bool = True


@dataclass
class Cenario:
    processo: str
    descricao: str
    divergencias_esperadas: list[str] = field(default_factory=list)
    documentos: list[Documento] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Formatação de números nos dois padrões
# ---------------------------------------------------------------------------

def fmt_br(valor: float, casas: int = 2) -> str:
    """1234.5 -> '1.234,50' (padrão brasileiro)."""
    texto = f"{valor:,.{casas}f}"  # '1,234.50'
    return texto.replace(",", "X").replace(".", ",").replace("X", ".")


def fmt_us(valor: float, casas: int = 2) -> str:
    """1234.5 -> '1,234.50' (padrão americano)."""
    return f"{valor:,.{casas}f}"


# ---------------------------------------------------------------------------
# Desenho dos PDFs
# ---------------------------------------------------------------------------

def _cabecalho(c: canvas.Canvas, titulo: str, subtitulo: str) -> float:
    """Desenha título e retorna a coordenada Y onde o conteúdo começa."""
    largura, altura = A4
    c.setFont("Helvetica-Bold", 16)
    c.drawString(20 * mm, altura - 25 * mm, titulo)
    c.setFont("Helvetica", 9)
    c.drawString(20 * mm, altura - 31 * mm, subtitulo)
    c.line(20 * mm, altura - 34 * mm, largura - 20 * mm, altura - 34 * mm)
    return altura - 44 * mm


def _linhas(c: canvas.Canvas, y: float, pares: list[tuple[str, str]]) -> float:
    """Escreve linhas 'Rótulo: valor'. Rótulo e valor ficam na mesma linha de
    texto, o que facilita a extração por expressão regular na Etapa 1."""
    c.setFont("Helvetica", 10)
    for rotulo, valor in pares:
        c.drawString(20 * mm, y, f"{rotulo}: {valor}")
        y -= 6 * mm
    return y - 4 * mm


def _tabela_itens(c: canvas.Canvas, y: float, colunas: list[str],
                  linhas: list[list[str]]) -> float:
    """Tabela simples com bordas (o pdfplumber reconhece tabelas pelas linhas)."""
    xs = [20, 85, 115, 135, 160, 190]  # posições das colunas em mm
    altura_linha = 7 * mm
    todas = [colunas] + linhas
    for i, linha in enumerate(todas):
        c.setFont("Helvetica-Bold" if i == 0 else "Helvetica", 9)
        topo = y - i * altura_linha
        for j, celula in enumerate(linha):
            c.drawString(xs[j] * mm + 1.5 * mm, topo - 5 * mm, celula)
    # grade
    base = y - len(todas) * altura_linha
    for i in range(len(todas) + 1):
        c.line(xs[0] * mm, y - i * altura_linha, xs[-1] * mm, y - i * altura_linha)
    for x in xs:
        c.line(x * mm, y, x * mm, base)
    return base - 8 * mm


def desenhar_nota_fiscal(caminho: Path, processo: str, numero: str, emissao: date,
                         itens: list[Item], valor_total: float,
                         peso_total: float | None) -> None:
    c = canvas.Canvas(str(caminho), pagesize=A4)
    c.setTitle(f"Nota Fiscal {numero}")
    y = _cabecalho(c, "NOTA FISCAL DE IMPORTACAO",
                   "Documento sintetico gerado para testes - sem validade fiscal")
    pares = [
        ("Numero da NF", numero),
        ("Processo", processo),
        ("Data de emissao", emissao.strftime("%d/%m/%Y")),
        ("Importador", IMPORTADOR),
        ("Exportador", EXPORTADOR),
    ]
    y = _linhas(c, y, pares)
    y = _tabela_itens(
        c, y,
        ["Descricao", "NCM", "Qtd", "Peso (kg)", "Valor (USD)"],
        [[i.descricao, i.ncm, str(i.quantidade), fmt_br(i.peso_kg, 3), fmt_br(i.valor_usd)]
         for i in itens],
    )
    totais = [("Valor total FOB (USD)", fmt_br(valor_total))]
    # Cenário "campo ausente": a linha de peso simplesmente não é impressa.
    if peso_total is not None:
        totais.append(("Peso liquido total (kg)", fmt_br(peso_total, 3)))
    _linhas(c, y, totais)
    c.showPage()
    c.save()


def desenhar_fatura(caminho: Path, processo: str, numero: str, emissao: date,
                    itens: list[Item], valor_total: float, peso_total: float) -> None:
    c = canvas.Canvas(str(caminho), pagesize=A4)
    c.setTitle(f"Commercial Invoice {numero}")
    y = _cabecalho(c, "COMMERCIAL INVOICE",
                   "Synthetic document generated for testing purposes only")
    pares = [
        ("Invoice No.", numero),
        ("Reference", processo),
        ("Date", emissao.isoformat()),
        ("Seller", EXPORTADOR),
        ("Buyer", IMPORTADOR),
        ("Incoterm", "FOB Shenzhen"),
    ]
    y = _linhas(c, y, pares)
    y = _tabela_itens(
        c, y,
        ["Description", "HS/NCM", "Qty", "Net kg", "Amount USD"],
        [[i.descricao, i.ncm, str(i.quantidade), fmt_us(i.peso_kg, 3), fmt_us(i.valor_usd)]
         for i in itens],
    )
    _linhas(c, y, [
        ("Total FOB (USD)", fmt_us(valor_total)),
        ("Total net weight (kg)", fmt_us(peso_total, 3)),
    ])
    c.showPage()
    c.save()


def gravar_pdf_corrompido(caminho: Path) -> None:
    """Arquivo com extensão .pdf mas conteúdo inválido (simula download truncado)."""
    caminho.write_bytes(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n1 0 obj << /Type /Catalog >>\n"
                        b"conteudo truncado durante o download\n")


# ---------------------------------------------------------------------------
# Montagem dos cenários
# ---------------------------------------------------------------------------

def sortear_itens(rng: random.Random, quantidade_itens: int) -> list[Item]:
    escolhidos = rng.sample(CATALOGO, quantidade_itens)
    itens = []
    for descricao, ncm, peso_unit, preco_unit in escolhidos:
        qtd = rng.randint(10, 400)
        itens.append(Item(descricao, ncm, qtd,
                          round(qtd * peso_unit, 3), round(qtd * preco_unit, 2)))
    return itens


def montar_cenarios(pasta: Path, rng: random.Random) -> list[Cenario]:
    # (processo, descrição, tipo de anomalia)
    roteiro = [
        ("PROC-2026-001", "Processo conforme", None),
        ("PROC-2026-002", "Processo conforme com 3 itens", None),
        ("PROC-2026-003", "Valor da NF diferente da fatura", "valor"),
        ("PROC-2026-004", "Peso da NF diferente da fatura", "peso"),
        ("PROC-2026-005", "Fatura comercial ausente", "sem_fatura"),
        ("PROC-2026-006", "NF sem a linha de peso total", "campo_ausente"),
        ("PROC-2026-007", "NF ilegivel (PDF corrompido)", "corrompido"),
        ("PROC-2026-008", "Processo conforme", None),
    ]
    base = date(2026, 10, 1)
    cenarios: list[Cenario] = []

    for idx, (processo, descricao, anomalia) in enumerate(roteiro, start=1):
        cen = Cenario(processo, descricao)
        itens = sortear_itens(rng, 3 if idx == 2 else rng.randint(1, 2))
        valor = round(sum(i.valor_usd for i in itens), 2)
        peso = round(sum(i.peso_kg for i in itens), 3)
        ncms = [i.ncm for i in itens]
        emissao_fatura = base + timedelta(days=idx * 2)
        emissao_nf = emissao_fatura + timedelta(days=rng.randint(5, 15))
        num_nf = f"NF-{100000 + idx * 37}"
        num_fatura = f"INV-2026-{idx:04d}"

        # Valores que vão para a NF (podem ser adulterados conforme o cenário).
        valor_nf, peso_nf = valor, peso
        if anomalia == "valor":
            valor_nf = round(valor + 1350.00, 2)
            cen.divergencias_esperadas.append("valor")
        elif anomalia == "peso":
            peso_nf = round(peso - 42.750, 3)
            cen.divergencias_esperadas.append("peso")
        elif anomalia == "campo_ausente":
            peso_nf = None
            cen.divergencias_esperadas.append("campo_ausente:peso_total_kg")
        elif anomalia == "sem_fatura":
            cen.divergencias_esperadas.append("documento_ausente:fatura_comercial")
        elif anomalia == "corrompido":
            cen.divergencias_esperadas.append("documento_ilegivel:nota_fiscal")

        # --- Nota fiscal ---
        arq_nf = f"{processo}_NF.pdf"
        if anomalia == "corrompido":
            gravar_pdf_corrompido(pasta / arq_nf)
            cen.documentos.append(Documento(arq_nf, "nota_fiscal", processo,
                                            None, None, None, None, [], legivel=False))
        else:
            desenhar_nota_fiscal(pasta / arq_nf, processo, num_nf, emissao_nf,
                                 itens, valor_nf, peso_nf)
            cen.documentos.append(Documento(arq_nf, "nota_fiscal", processo, num_nf,
                                            emissao_nf.isoformat(), valor_nf, peso_nf, ncms))

        # --- Fatura comercial ---
        if anomalia != "sem_fatura":
            arq_fat = f"{processo}_FATURA.pdf"
            desenhar_fatura(pasta / arq_fat, processo, num_fatura, emissao_fatura,
                            itens, valor, peso)
            cen.documentos.append(Documento(arq_fat, "fatura_comercial", processo,
                                            num_fatura, emissao_fatura.isoformat(),
                                            valor, peso, ncms))
        cenarios.append(cen)
    return cenarios


def main() -> None:
    parser = argparse.ArgumentParser(description="Gera PDFs sintéticos de importação.")
    parser.add_argument("--saida", default="dados/entrada", help="pasta de destino")
    parser.add_argument("--gabarito", default="dados/gabarito.json",
                        help="arquivo JSON com os valores esperados")
    args = parser.parse_args()

    pasta = Path(args.saida)
    pasta.mkdir(parents=True, exist_ok=True)
    rng = random.Random(SEMENTE)
    cenarios = montar_cenarios(pasta, rng)

    gabarito = Path(args.gabarito)
    gabarito.parent.mkdir(parents=True, exist_ok=True)
    gabarito.write_text(json.dumps([asdict(c) for c in cenarios],
                                   ensure_ascii=False, indent=2), encoding="utf-8")

    total = sum(len(c.documentos) for c in cenarios)
    print(f"Gerados {total} PDFs em {pasta} para {len(cenarios)} processos.")
    for c in cenarios:
        marca = "OK " if not c.divergencias_esperadas else "!! "
        print(f"  {marca}{c.processo}  {c.descricao}")
    print(f"Gabarito: {gabarito}")


if __name__ == "__main__":
    main()
