# despachante-digital/src/despachante/email_envio.py
"""Envio do relatório por e-mail via SMTP com STARTTLS (Etapa 5).

As credenciais vêm só da Config (variáveis de ambiente). Se o e-mail não
estiver configurado, o envio é pulado com um aviso, sem quebrar o lote.
"""

from __future__ import annotations

import logging
import smtplib
from email.message import EmailMessage
from pathlib import Path

from despachante.config import Config

log = logging.getLogger(__name__)

TIPO_XLSX = ("application", "vnd.openxmlformats-officedocument.spreadsheetml.sheet")


def montar_mensagem(config: Config, assunto: str, html: str,
                    anexos: list[Path] | None = None) -> EmailMessage:
    msg = EmailMessage()
    msg["Subject"] = assunto
    msg["From"] = config.email_remetente
    msg["To"] = ", ".join(config.email_destinatarios)
    msg.set_content("Seu cliente de e-mail não exibe HTML. Veja o relatório anexo.")
    msg.add_alternative(html, subtype="html")
    for anexo in anexos or []:
        anexo = Path(anexo)
        if anexo.suffix == ".xlsx":
            principal, sub = TIPO_XLSX
        else:
            principal, sub = "text", "html"
        msg.add_attachment(anexo.read_bytes(), maintype=principal, subtype=sub,
                           filename=anexo.name)
    return msg


def enviar_relatorio(config: Config, assunto: str, html: str,
                     anexos: list[Path] | None = None) -> bool:
    """Envia e devolve True; devolve False (e registra) se não configurado ou falhar."""
    if not config.email_configurado:
        log.warning("email_nao_configurado",
                    extra={"dica": "defina SMTP_USUARIO, SMTP_SENHA e EMAIL_DESTINATARIOS"})
        return False
    msg = montar_mensagem(config, assunto, html, anexos)
    try:
        with smtplib.SMTP(config.smtp_host, config.smtp_porta, timeout=30) as smtp:
            smtp.starttls()
            smtp.login(config.smtp_usuario, config.smtp_senha)
            smtp.send_message(msg)
    except (smtplib.SMTPException, OSError) as erro:
        log.error("email_falhou", extra={"erro": str(erro)})
        return False
    log.info("email_enviado", extra={"destinatarios": config.email_destinatarios})
    return True
