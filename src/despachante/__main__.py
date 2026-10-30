# despachante-digital/src/despachante/__main__.py
"""Linha de comando.

    python -m despachante lote        processa a entrada uma vez e gera as saídas
    python -m despachante relatorio   só gera as saídas a partir do registro
    python -m despachante monitorar   monitor contínuo + relatório agendado
Use --sem-email para não enviar e-mail.
"""

from __future__ import annotations

import argparse
import logging
import time

from despachante.agendador import criar_agendador
from despachante.config import carregar_config
from despachante.logs import configurar_logs
from despachante.monitor import iniciar_monitor
from despachante.pipeline import executar_lote, gerar_saidas
from despachante.registro import Registro

log = logging.getLogger("despachante")


def main() -> None:
    parser = argparse.ArgumentParser(prog="despachante", description="Despachante Digital")
    parser.add_argument("comando", choices=["lote", "relatorio", "monitorar"])
    parser.add_argument("--sem-email", action="store_true", help="não envia o e-mail")
    args = parser.parse_args()

    config = carregar_config()
    config.criar_pastas()
    configurar_logs(config.pasta_logs)
    registro = Registro(config.arquivo_registro)

    if args.comando in ("lote", "relatorio"):
        if args.comando == "lote":
            r = executar_lote(config, registro, enviar_email=not args.sem_email)
        else:
            r = gerar_saidas(config, registro, enviar_email=not args.sem_email)
        print(f"\nResumo: {r.resumo}")
        print(f"Planilha:  {r.planilha}")
        print(f"Relatorio: {r.relatorio}")
        print(f"E-mail enviado: {'sim' if r.email_enviado else 'nao'}")
        return

    observador = iniciar_monitor(config, registro)
    agendador = criar_agendador(config, registro)
    agendador.start()
    proximo = agendador.get_job("relatorio_diario").next_run_time
    log.info("servico_no_ar", extra={"proximo_relatorio": str(proximo)})
    print(f"Monitorando {config.pasta_entrada}. Proximo relatorio: {proximo}. Ctrl+C para sair.")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        agendador.shutdown(wait=False)
        observador.stop()
        observador.join()
        log.info("servico_encerrado")


if __name__ == "__main__":
    main()
