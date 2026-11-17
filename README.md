# Cupons em Lote · VTEX

App para criar cupons com **códigos personalizados** em massa na VTEX, usando o endpoint
`POST /api/rnb/pvt/multiple-coupons`. Funciona na web (Vercel) ou rodando no seu PC.

## O que faz

- Lê os códigos de uma planilha **.xlsx**, **.csv** ou **.txt**, no próprio navegador, e detecta sozinho a coluna dos cupons
- Remove duplicados e separa os códigos inválidos (com espaço ou caractere especial)
- Vincula todos os cupons à promoção pela **utm_source** e pela **utm_campaign**
- Testa as credenciais e verifica quais códigos já existem na loja antes de enviar
- Envia em lotes, com nova tentativa automática em erros 429/5xx, barra de progresso e log
- Gera um relatório CSV com o status de cada cupom

## Estrutura

```
public/index.html           interface
public/vendor/              SheetJS (leitura de planilhas no navegador)
api/vtex.js                 proxy da Vercel para a API da VTEX
vercel.json
local/app.py                mesmo proxy em Python, para rodar no PC
local/Abrir Cupons em Lote.bat
```

## Por que existe um proxy

A API privada da VTEX não aceita chamadas feitas direto pelo navegador (CORS). Por isso a página chama
`/api/vtex`, que repassa a requisição para a loja. O proxy:

- só permite três rotas: testar a conexão (`GET .../benefits/calculatorconfiguration`), listar os cupons (`GET .../coupon`) e criar cupons (`POST .../multiple-coupons`)
- só aceita domínios `{account}.vtexcommercestable.com.br` ou `{account}.vtexcommercebeta.com.br`
- não grava nada: AppKey e AppToken vêm em cada requisição e não ficam salvos no servidor

A AppKey precisa de permissão no módulo de **Promoções e Impostos** (Rates and Benefits).

## Versão web (Vercel)

Cada push na `main` publica uma nova versão automaticamente. A Vercel não precisa de nenhuma variável de ambiente.

## Versão local (Windows)

1. Instale o [Python](https://www.python.org/downloads/) marcando **"Add Python to PATH"**.
2. Baixe o repositório (**Code → Download ZIP**) e extraia.
3. Dê dois cliques em `local/Abrir Cupons em Lote.bat`. O app abre em `http://127.0.0.1:5000`.
