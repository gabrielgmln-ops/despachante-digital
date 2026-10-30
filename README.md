# Despachante Digital

Automação que processa documentos de importação em lote: monitora uma pasta, extrai os dados de cada PDF (nota fiscal e fatura comercial), agrupa por processo, aponta divergências entre os documentos, consolida tudo numa planilha Excel e envia um relatório HTML por e-mail no horário agendado.

> Todos os documentos são **sintéticos**, gerados por `scripts/gerar_pdfs.py`. Nenhum dado real.

## Fluxo

```
dados/entrada/*.pdf ──► monitor (watchdog) ──► extração (pdfplumber)
                                                   │
                       ┌───────────────────────────┤
                       ▼                           ▼
             dados/processados/          dados/erros/  (ilegível)
                       │
                       ▼
             registro.json ──► agrupamento + divergências
                                     │
                     ┌───────────────┼────────────────┐
                     ▼               ▼                ▼
             consolidado.xlsx  relatorio.html   e-mail (SMTP)
                                     ▲
                          APScheduler (cron)
```

## O que é detectado

| Divergência | Regra |
|---|---|
| `valor` | valor FOB da NF difere da fatura além de `TOLERANCIA_VALOR_USD` |
| `peso` | peso líquido difere além de `TOLERANCIA_PESO_KG` |
| `ncm` | conjunto de NCMs diferente entre NF e fatura |
| `campo_ausente` | campo obrigatório não encontrado no PDF |
| `documento_ausente` | processo sem NF ou sem fatura |
| `documento_ilegivel` | PDF corrompido ou sem texto (vai para `dados/erros/`) |

Nenhum erro para o lote: cada PDF problemático é registrado, movido e o processamento continua.

## Como rodar

```bash
python -m venv .venv
.venv\Scripts\activate          # Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt -e .
copy .env.example .env          # preencha o SMTP se quiser e-mail
python scripts/gerar_pdfs.py    # 15 PDFs sintéticos em dados/entrada
```

| Comando | O que faz |
|---|---|
| `python -m despachante lote` | processa a entrada uma vez e gera planilha + relatório + e-mail |
| `python -m despachante relatorio` | só gera as saídas a partir do que já foi registrado |
| `python -m despachante monitorar` | monitor contínuo + relatório no horário de `CRON_RELATORIO` |

Acrescente `--sem-email` para não enviar. Sem `SMTP_USUARIO`/`SMTP_SENHA`/`EMAIL_DESTINATARIOS`, o envio é pulado com aviso no log.

Saída esperada de `lote` com os PDFs sintéticos:

```
Resumo: {'total': 8, 'conformes': 3, 'divergentes': 5, 'divergencias': 5, 'erros': 1}
```

### E-mail (Gmail)

Use uma **senha de app** (Conta Google → Segurança → Senhas de app), nunca a senha da conta. Ela fica só no `.env`, que não é versionado.

## Testes

```bash
pytest
```

23 testes: extração comparada a um gabarito, monitor com arquivo real chegando na pasta, divergências por cenário, abas da planilha, relatório, e-mail com SMTP falso, logs JSON, agendador e o lote ponta a ponta.

## Logs

Uma linha JSON por evento, no console e em `logs/despachante.log` (rotativo, 5 × 1 MB):

```json
{"quando": "2026-10-30T12:37:15+00:00", "nivel": "ERROR", "modulo": "despachante.monitor", "evento": "documento_rejeitado", "arquivo": "PROC-2026-007_NF.pdf", "motivo": "..."}
```

## Fora do escopo

OCR de documentos escaneados e interface gráfica.

## Stack

Python 3.12+ · watchdog · pdfplumber · pandas + openpyxl · Jinja2 · smtplib · APScheduler · pytest · reportlab (só no gerador)
