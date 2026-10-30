# despachante-digital/tests/conftest.py
"""Fixtures compartilhadas: um lote sintético gerado uma única vez por sessão."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="session")
def lote_sintetico(tmp_path_factory) -> tuple[Path, list[dict]]:
    """Gera os 15 PDFs e devolve (pasta, gabarito)."""
    pasta = tmp_path_factory.mktemp("lote")
    gabarito = pasta.parent / "gabarito_sessao.json"
    subprocess.run(
        [sys.executable, str(RAIZ / "scripts" / "gerar_pdfs.py"),
         "--saida", str(pasta), "--gabarito", str(gabarito)],
        check=True, capture_output=True,
    )
    return pasta, json.loads(gabarito.read_text(encoding="utf-8"))


@pytest.fixture
def documentos_gabarito(lote_sintetico) -> dict[str, dict]:
    """Gabarito indexado pelo nome do arquivo."""
    _, cenarios = lote_sintetico
    return {d["arquivo"]: d for c in cenarios for d in c["documentos"]}
