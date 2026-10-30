# despachante-digital/tests/test_relatorio_email.py
"""Testes da Etapa 5: relatório HTML e envio por e-mail (SMTP falso)."""

import smtplib
from dataclasses import replace

import pytest

from despachante.agrupamento import analisar
from despachante.config import Config
from despachante.email_envio import enviar_relatorio
from despachante.extracao import PdfIlegivelError, extrair_documento
from despachante.relatorio import renderizar_relatorio


@pytest.fixture
def analise(lote_sintetico):
    pasta, _ = lote_sintetico
    docs, erros = [], {}
    for pdf in sorted(pasta.glob("*.pdf")):
        try:
            docs.append(extrair_documento(pdf))
        except PdfIlegivelError as e:
            erros[pdf.name] = {"motivo": str(e)}
    return analisar(docs, erros), erros


class SmtpFalso:
    """Substitui smtplib.SMTP: guarda o que seria enviado em vez de enviar."""
    enviados: list = []

    def __init__(self, host, porta, timeout=None):
        self.host, self.porta = host, porta

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def starttls(self):
        pass

    def login(self, usuario, senha):
        if senha != "senha-de-teste":
            raise smtplib.SMTPAuthenticationError(535, b"credenciais invalidas")

    def send_message(self, msg):
        SmtpFalso.enviados.append(msg)


CONFIG_EMAIL = replace(Config(), smtp_usuario="robo@exemplo.test", smtp_senha="senha-de-teste",
                       email_remetente="robo@exemplo.test",
                       email_destinatarios=["equipe@exemplo.test"])


def test_relatorio_lista_processos_e_divergencias(analise):
    html = renderizar_relatorio(*analise)
    for n in range(1, 9):
        assert f"PROC-2026-00{n}" in html
    assert "DIVERGENTE" in html and "CONFORME" in html
    assert "PROC-2026-007_NF.pdf" in html
    assert "<script>" not in html


def test_envia_email_com_anexo(analise, tmp_path, monkeypatch):
    SmtpFalso.enviados = []
    monkeypatch.setattr(smtplib, "SMTP", SmtpFalso)
    anexo = tmp_path / "consolidado.xlsx"
    anexo.write_bytes(b"planilha")
    assert enviar_relatorio(CONFIG_EMAIL, "Relatorio", renderizar_relatorio(*analise), [anexo])
    msg = SmtpFalso.enviados[0]
    assert msg["To"] == "equipe@exemplo.test"
    assert [p.get_filename() for p in msg.iter_attachments()] == ["consolidado.xlsx"]


def test_sem_configuracao_nao_envia(monkeypatch):
    monkeypatch.setattr(smtplib, "SMTP", SmtpFalso)
    assert enviar_relatorio(Config(), "x", "<p>x</p>") is False


def test_falha_de_login_nao_levanta(monkeypatch):
    monkeypatch.setattr(smtplib, "SMTP", SmtpFalso)
    config = replace(CONFIG_EMAIL, smtp_senha="errada")
    assert enviar_relatorio(config, "x", "<p>x</p>") is False
