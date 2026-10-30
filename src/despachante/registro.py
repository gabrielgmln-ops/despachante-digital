# despachante-digital/src/despachante/registro.py
"""Registro persistente dos documentos processados (arquivo JSON).

O monitor grava aqui cada documento extraído (ou o erro dele); o relatório
lê daqui. Assim o relatório agendado enxerga tudo que chegou desde o início,
mesmo que o monitor tenha sido reiniciado no meio do caminho.
"""

from __future__ import annotations

import json
import threading
from datetime import datetime
from pathlib import Path

from despachante.extracao import DocumentoExtraido


class Registro:
    def __init__(self, caminho: Path):
        self.caminho = Path(caminho)
        # O watchdog chama de outra thread; o agendador, de outra ainda.
        self._trava = threading.Lock()

    def _ler(self) -> dict:
        if not self.caminho.exists():
            return {"documentos": {}, "erros": {}}
        return json.loads(self.caminho.read_text(encoding="utf-8"))

    def _gravar(self, dados: dict) -> None:
        self.caminho.parent.mkdir(parents=True, exist_ok=True)
        temporario = self.caminho.with_suffix(".tmp")
        temporario.write_text(json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8")
        temporario.replace(self.caminho)  # troca atômica: nunca deixa JSON pela metade

    def salvar_documento(self, doc: DocumentoExtraido) -> None:
        with self._trava:
            dados = self._ler()
            dados["documentos"][doc.arquivo] = doc.para_dict()
            dados["erros"].pop(doc.arquivo, None)
            self._gravar(dados)

    def salvar_erro(self, arquivo: str, motivo: str) -> None:
        with self._trava:
            dados = self._ler()
            dados["erros"][arquivo] = {"motivo": motivo,
                                       "quando": datetime.now().isoformat(timespec="seconds")}
            self._gravar(dados)

    def documentos(self) -> list[DocumentoExtraido]:
        with self._trava:
            return [DocumentoExtraido(**d) for d in self._ler()["documentos"].values()]

    def erros(self) -> dict[str, dict]:
        with self._trava:
            return self._ler()["erros"]
