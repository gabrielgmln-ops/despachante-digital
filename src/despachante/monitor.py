# despachante-digital/src/despachante/monitor.py
"""Monitor de pasta (Etapa 2).

Cada PDF que aparece na pasta de entrada é:
  1. aguardado até terminar de ser copiado (tamanho estável);
  2. extraído;
  3. registrado no Registro;
  4. movido para `processados/` (sucesso) ou `erros/` (ilegível ou desconhecido).

Um arquivo com problema é registrado e movido, e o monitor continua no próximo.
"""

from __future__ import annotations

import logging
import shutil
import time
from pathlib import Path

from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

from despachante.config import Config
from despachante.extracao import PdfIlegivelError, TipoDesconhecidoError, extrair_documento
from despachante.registro import Registro

log = logging.getLogger(__name__)


def aguardar_arquivo_estavel(caminho: Path, intervalo: float = 0.3, tentativas: int = 20) -> bool:
    """Espera o tamanho parar de mudar. Evita ler um PDF ainda sendo copiado,
    porque o evento 'created' dispara no primeiro byte, não no último."""
    tamanho_anterior = -1
    for _ in range(tentativas):
        try:
            tamanho = caminho.stat().st_size
        except FileNotFoundError:
            return False
        if tamanho == tamanho_anterior and tamanho > 0:
            return True
        tamanho_anterior = tamanho
        time.sleep(intervalo)
    return False


def _mover(origem: Path, pasta_destino: Path) -> Path:
    pasta_destino.mkdir(parents=True, exist_ok=True)
    destino = pasta_destino / origem.name
    if destino.exists():  # mesmo nome chegou de novo: preserva os dois
        destino = pasta_destino / f"{origem.stem}_{int(time.time())}{origem.suffix}"
    shutil.move(str(origem), destino)
    return destino


def processar_arquivo(caminho: Path, config: Config, registro: Registro) -> bool:
    """Processa um PDF. Retorna True se foi extraído, False se foi para erros."""
    caminho = Path(caminho)
    try:
        doc = extrair_documento(caminho)
    except (PdfIlegivelError, TipoDesconhecidoError) as erro:
        registro.salvar_erro(caminho.name, str(erro))
        _mover(caminho, config.pasta_erros)
        log.error("documento_rejeitado", extra={"arquivo": caminho.name, "motivo": str(erro)})
        return False
    except Exception as erro:  # qualquer surpresa também não pode parar o lote
        registro.salvar_erro(caminho.name, f"erro inesperado: {erro}")
        _mover(caminho, config.pasta_erros)
        log.exception("erro_inesperado", extra={"arquivo": caminho.name})
        return False

    registro.salvar_documento(doc)
    _mover(caminho, config.pasta_processados)
    if doc.campos_ausentes:
        log.warning("campos_ausentes", extra={"arquivo": doc.arquivo,
                                              "campos": doc.campos_ausentes})
    log.info("documento_extraido", extra={"arquivo": doc.arquivo, "tipo": doc.tipo,
                                          "processo": doc.processo})
    return True


def processar_pendentes(config: Config, registro: Registro) -> int:
    """Processa os PDFs que já estavam na pasta antes do monitor subir."""
    pdfs = sorted(config.pasta_entrada.glob("*.pdf"))
    for pdf in pdfs:
        processar_arquivo(pdf, config, registro)
    return len(pdfs)


class _ManipuladorPdf(FileSystemEventHandler):
    def __init__(self, config: Config, registro: Registro):
        self.config = config
        self.registro = registro

    def _talvez_processar(self, caminho_str: str) -> None:
        caminho = Path(caminho_str)
        if caminho.suffix.lower() != ".pdf":
            return
        if aguardar_arquivo_estavel(caminho):
            processar_arquivo(caminho, self.config, self.registro)

    def on_created(self, event: FileSystemEvent) -> None:
        if not event.is_directory:
            self._talvez_processar(event.src_path)

    def on_moved(self, event: FileSystemEvent) -> None:
        # Muitos programas gravam "x.tmp" e renomeiam para "x.pdf" no fim.
        if not event.is_directory:
            self._talvez_processar(event.dest_path)


def iniciar_monitor(config: Config, registro: Registro) -> Observer:
    """Processa o que já existe e liga o observador. Quem chama faz o stop()."""
    config.criar_pastas()
    pendentes = processar_pendentes(config, registro)
    observador = Observer()
    observador.schedule(_ManipuladorPdf(config, registro), str(config.pasta_entrada),
                        recursive=False)
    observador.start()
    log.info("monitor_iniciado", extra={"pasta": str(config.pasta_entrada),
                                        "pendentes_processados": pendentes})
    return observador
