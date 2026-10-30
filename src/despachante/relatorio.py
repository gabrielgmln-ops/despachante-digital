# despachante-digital/src/despachante/relatorio.py
"""Relatório HTML com Jinja2 (Etapa 5)."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from despachante.agrupamento import Processo

PASTA_TEMPLATES = Path(__file__).parent / "templates"


def _moeda(valor: float | None) -> str:
    """Formato brasileiro: 12.345,67 (o relatório é lido por brasileiros)."""
    if valor is None:
        return "ausente"
    return f"{valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _peso(valor: float | None) -> str:
    if valor is None:
        return "ausente"
    return f"{valor:,.3f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _ambiente() -> Environment:
    # autoescape: um nome de arquivo com "<script>" vira texto, não código.
    env = Environment(loader=FileSystemLoader(PASTA_TEMPLATES),
                      autoescape=select_autoescape(["html", "j2"]))
    env.filters["moeda"] = _moeda
    env.filters["peso"] = _peso
    return env


def resumir(processos: dict[str, Processo], erros: dict[str, dict]) -> dict:
    divergentes = sum(1 for p in processos.values() if p.status == "DIVERGENTE")
    return {
        "total": len(processos),
        "conformes": len(processos) - divergentes,
        "divergentes": divergentes,
        "divergencias": sum(len(p.divergencias) for p in processos.values()),
        "erros": len(erros),
    }


def renderizar_relatorio(processos: dict[str, Processo], erros: dict[str, dict],
                         gerado_em: datetime | None = None) -> str:
    gerado_em = gerado_em or datetime.now()
    return _ambiente().get_template("relatorio.html.j2").render(
        gerado_em=gerado_em.strftime("%d/%m/%Y %H:%M"),
        resumo=resumir(processos, erros),
        processos=list(processos.values()),
        divergencias=[d for p in processos.values() for d in p.divergencias],
        erros=erros,
    )


def salvar_relatorio(html: str, destino: Path) -> Path:
    destino = Path(destino)
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(html, encoding="utf-8")
    return destino
