# despachante-digital/src/despachante/extracao.py
"""Extração de campos de um PDF de importação (Etapa 1).

Reconhece dois tipos de documento:
  - nota_fiscal: números no padrão brasileiro (1.234,56) e data dd/mm/aaaa
  - fatura_comercial: números no padrão americano (1,234.56) e data aaaa-mm-dd

Erros são tratados assim, para nunca derrubar o lote:
  - PDF que não abre ou não tem texto  -> levanta PdfIlegivelError
  - campo obrigatório não encontrado   -> o documento volta com o campo None
                                          e o nome dele em `campos_ausentes`
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path

import pdfplumber

CAMPOS_OBRIGATORIOS = ("numero", "processo", "data", "valor_total_usd", "peso_total_kg")


class PdfIlegivelError(Exception):
    """O arquivo não pôde ser aberto ou não contém texto extraível."""


class TipoDesconhecidoError(Exception):
    """O PDF abriu, mas não é nota fiscal nem fatura comercial."""


@dataclass
class DocumentoExtraido:
    arquivo: str
    tipo: str
    processo: str | None = None
    numero: str | None = None
    data: str | None = None              # sempre ISO (aaaa-mm-dd)
    valor_total_usd: float | None = None
    peso_total_kg: float | None = None
    ncms: list[str] = field(default_factory=list)
    campos_ausentes: list[str] = field(default_factory=list)

    def para_dict(self) -> dict:
        return asdict(self)


# ---------------------------------------------------------------------------
# Conversão de números nos dois padrões
# ---------------------------------------------------------------------------

def numero_br(texto: str) -> float:
    """'1.250,500' -> 1250.5"""
    return float(texto.replace(".", "").replace(",", "."))


def numero_us(texto: str) -> float:
    """'1,250.500' -> 1250.5"""
    return float(texto.replace(",", ""))


# Cada tipo de documento tem seus rótulos, formato de número e de data.
# O padrão de número `[\d.,]+` aceita os dois formatos; a função de conversão
# é quem sabe qual separador é o decimal.
LAYOUTS = {
    "nota_fiscal": {
        "assinatura": "NOTA FISCAL DE IMPORTACAO",
        "numero": r"Numero da NF:\s*(\S+)",
        "processo": r"Processo:\s*(\S+)",
        "data": r"Data de emissao:\s*(\d{2}/\d{2}/\d{4})",
        "formato_data": "%d/%m/%Y",
        "valor_total_usd": r"Valor total FOB \(USD\):\s*([\d.,]+)",
        "peso_total_kg": r"Peso liquido total \(kg\):\s*([\d.,]+)",
        "converter": numero_br,
    },
    "fatura_comercial": {
        "assinatura": "COMMERCIAL INVOICE",
        "numero": r"Invoice No\.:\s*(\S+)",
        "processo": r"Reference:\s*(\S+)",
        "data": r"Date:\s*(\d{4}-\d{2}-\d{2})",
        "formato_data": "%Y-%m-%d",
        "valor_total_usd": r"Total FOB \(USD\):\s*([\d.,]+)",
        "peso_total_kg": r"Total net weight \(kg\):\s*([\d.,]+)",
        "converter": numero_us,
    },
}

PADRAO_NCM = re.compile(r"^\d{4}\.\d{2}\.\d{2}$")


def _ler_pdf(caminho: Path) -> tuple[str, list[list[list[str | None]]]]:
    """Abre o PDF e devolve (texto de todas as páginas, tabelas encontradas)."""
    try:
        with pdfplumber.open(caminho) as pdf:
            textos, tabelas = [], []
            for pagina in pdf.pages:
                textos.append(pagina.extract_text() or "")
                tabelas.extend(pagina.extract_tables())
    except Exception as erro:  # pdfminer levanta vários tipos diferentes
        raise PdfIlegivelError(f"{caminho.name}: não foi possível abrir ({erro})") from erro
    texto = "\n".join(textos).strip()
    if not texto:
        raise PdfIlegivelError(f"{caminho.name}: PDF sem texto (escaneado?)")
    return texto, tabelas


def _ncms_das_tabelas(tabelas: list) -> list[str]:
    """Procura a coluna cujo cabeçalho contém 'NCM' e coleta os códigos válidos."""
    ncms: list[str] = []
    for tabela in tabelas:
        if not tabela:
            continue
        cabecalho = [(c or "").upper() for c in tabela[0]]
        col = next((i for i, c in enumerate(cabecalho) if "NCM" in c), None)
        if col is None:
            continue
        for linha in tabela[1:]:
            valor = (linha[col] or "").strip()
            if PADRAO_NCM.match(valor) and valor not in ncms:
                ncms.append(valor)
    return ncms


def identificar_tipo(texto: str) -> str:
    for tipo, layout in LAYOUTS.items():
        if layout["assinatura"] in texto:
            return tipo
    raise TipoDesconhecidoError("documento não reconhecido como NF nem fatura comercial")


def extrair_documento(caminho: str | Path) -> DocumentoExtraido:
    """Extrai os campos de um PDF. Ver docstring do módulo para o tratamento de erros."""
    caminho = Path(caminho)
    texto, tabelas = _ler_pdf(caminho)
    tipo = identificar_tipo(texto)
    layout = LAYOUTS[tipo]
    doc = DocumentoExtraido(arquivo=caminho.name, tipo=tipo)

    for campo in CAMPOS_OBRIGATORIOS:
        achado = re.search(layout[campo], texto)
        if not achado:
            doc.campos_ausentes.append(campo)
            continue
        bruto = achado.group(1)
        try:
            if campo == "data":
                valor = datetime.strptime(bruto, layout["formato_data"]).date().isoformat()
            elif campo in ("valor_total_usd", "peso_total_kg"):
                valor = layout["converter"](bruto)
            else:
                valor = bruto
        except ValueError:
            # Rótulo presente mas valor mal formatado conta como ausente.
            doc.campos_ausentes.append(campo)
            continue
        setattr(doc, campo, valor)

    doc.ncms = _ncms_das_tabelas(tabelas)
    if not doc.ncms:
        doc.campos_ausentes.append("ncms")
    return doc
