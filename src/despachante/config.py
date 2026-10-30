# despachante-digital/src/despachante/config.py
"""Configuração lida de variáveis de ambiente (com .env opcional).

Credenciais nunca ficam no código: só existem no ambiente ou no .env local.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv


def _lista(valor: str) -> list[str]:
    return [v.strip() for v in valor.split(",") if v.strip()]


@dataclass(frozen=True)
class Config:
    pasta_entrada: Path = Path("dados/entrada")
    pasta_processados: Path = Path("dados/processados")
    pasta_erros: Path = Path("dados/erros")
    pasta_saida: Path = Path("dados/saida")
    pasta_logs: Path = Path("logs")
    tolerancia_valor_usd: float = 0.01
    tolerancia_peso_kg: float = 0.5
    smtp_host: str = "smtp.gmail.com"
    smtp_porta: int = 587
    smtp_usuario: str = ""
    smtp_senha: str = field(default="", repr=False)  # nunca aparece em logs/repr
    email_remetente: str = ""
    email_destinatarios: list[str] = field(default_factory=list)
    cron_relatorio: str = "0 18 * * 1-5"

    @property
    def arquivo_registro(self) -> Path:
        """Banco simples (JSON) com todos os documentos já extraídos."""
        return self.pasta_saida / "registro.json"

    def criar_pastas(self) -> None:
        for pasta in (self.pasta_entrada, self.pasta_processados, self.pasta_erros,
                      self.pasta_saida, self.pasta_logs):
            pasta.mkdir(parents=True, exist_ok=True)

    @property
    def email_configurado(self) -> bool:
        return bool(self.smtp_usuario and self.smtp_senha and self.email_destinatarios)


def carregar_config() -> Config:
    load_dotenv()  # não sobrescreve variáveis que já existem no ambiente
    e = os.environ.get
    return Config(
        pasta_entrada=Path(e("PASTA_ENTRADA", "dados/entrada")),
        pasta_processados=Path(e("PASTA_PROCESSADOS", "dados/processados")),
        pasta_erros=Path(e("PASTA_ERROS", "dados/erros")),
        pasta_saida=Path(e("PASTA_SAIDA", "dados/saida")),
        pasta_logs=Path(e("PASTA_LOGS", "logs")),
        tolerancia_valor_usd=float(e("TOLERANCIA_VALOR_USD", "0.01")),
        tolerancia_peso_kg=float(e("TOLERANCIA_PESO_KG", "0.5")),
        smtp_host=e("SMTP_HOST", "smtp.gmail.com"),
        smtp_porta=int(e("SMTP_PORTA", "587")),
        smtp_usuario=e("SMTP_USUARIO", ""),
        smtp_senha=e("SMTP_SENHA", ""),
        email_remetente=e("EMAIL_REMETENTE", "") or e("SMTP_USUARIO", ""),
        email_destinatarios=_lista(e("EMAIL_DESTINATARIOS", "")),
        cron_relatorio=e("CRON_RELATORIO", "0 18 * * 1-5"),
    )
