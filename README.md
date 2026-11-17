# Cupons em Lote · VTEX

App local para criar cupons com **códigos personalizados** em massa na VTEX, usando o endpoint
`POST /api/rnb/pvt/multiple-coupons`.

## O que faz

- Lê os códigos de uma planilha **.xlsx**, **.csv** ou **.txt** e detecta sozinho a coluna dos cupons
- Remove duplicados e separa códigos inválidos (com espaço ou caractere especial)
- Vincula todos os cupons à promoção pela **utm_source** / **utm_campaign**
- Testa as credenciais antes de enviar
- Verifica quais códigos já existem na loja (eles seriam atualizados, não duplicados)
- Envia em lotes, com nova tentativa automática em erros 429/5xx, barra de progresso e log
- Gera um relatório CSV com o status de cada cupom

## Como usar (Windows)

1. Instale o [Python](https://www.python.org/downloads/) marcando **"Add Python to PATH"**.
2. Baixe este repositório (**Code → Download ZIP**) e extraia.
3. Dê dois cliques em **`Abrir Cupons em Lote.bat`**.
4. O app abre no navegador em `http://127.0.0.1:5000`. Deixe a janela preta aberta enquanto usa.

Em outro sistema:

```bash
pip install -r requirements.txt
python app.py
```

## Credenciais

A AppKey precisa de permissão no módulo de **Promoções e Impostos** (Rates and Benefits).
As credenciais ficam só na sua máquina: o navegador conversa com o servidor local (`app.py`), e é ele
quem chama a API da VTEX. Nada é salvo em disco, a não ser que você marque "Lembrar chave e token
neste PC" (fica no localStorage do navegador).

## Por que não roda direto no GitHub Pages

A API privada da VTEX bloqueia chamadas feitas pelo navegador (CORS). Para publicar na web,
é preciso um proxy, como uma serverless function na Vercel ou um Cloudflare Worker, entre a página e a VTEX.

## Estrutura

```
app.py                      servidor local (Flask) e chamadas à VTEX
static/index.html           interface
requirements.txt
Abrir Cupons em Lote.bat    launcher para Windows
```
