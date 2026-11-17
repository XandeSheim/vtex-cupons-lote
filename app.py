"""
VTEX · Cupons em lote
App local para criar cupons com códigos personalizados na VTEX
(POST /api/rnb/pvt/multiple-coupons).

Rodar:  python app.py   ->  abre http://127.0.0.1:5000
As credenciais ficam só na sua máquina: o navegador fala com este servidor
local, e é ele que chama a API da VTEX.
"""
import csv
import io
import os
import threading
import time
import uuid
import webbrowser

import openpyxl
import requests
from flask import Flask, Response, jsonify, request, send_from_directory

HOST = "127.0.0.1"
PORT = int(os.environ.get("PORT", "5000"))
# Só para testes: aponta para um servidor falso no lugar da VTEX.
BASE_URL_OVERRIDE = os.environ.get("VTEX_BASE_URL")

app = Flask(__name__, static_folder="static")
JOBS = {}


# ---------------------------------------------------------------- helpers
def base_url(account, env):
    if BASE_URL_OVERRIDE:
        return BASE_URL_OVERRIDE.rstrip("/")
    account = (account or "").strip()
    env = (env or "vtexcommercestable").strip()
    return f"https://{account}.{env}.com.br"


def vtex_headers(app_key, app_token):
    return {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "X-VTEX-API-AppKey": (app_key or "").strip(),
        "X-VTEX-API-AppToken": (app_token or "").strip(),
    }


def need(data, *fields):
    missing = [f for f in fields if not str(data.get(f) or "").strip()]
    if missing:
        return jsonify(ok=False, error="Campos obrigatórios: " + ", ".join(missing)), 400
    return None


def read_table(filename, raw):
    name = filename.lower()
    if name.endswith((".xlsx", ".xlsm")):
        wb = openpyxl.load_workbook(io.BytesIO(raw), read_only=True, data_only=True)
        sheets = {}
        for ws in wb.worksheets:
            rows = [
                ["" if v is None else str(v).strip() for v in r]
                for r in ws.iter_rows(values_only=True)
            ]
            rows = [r for r in rows if any(c for c in r)]
            if rows:
                sheets[ws.title] = rows
        return sheets
    text = raw.decode("utf-8-sig", errors="replace")
    if name.endswith(".txt"):
        return {"Lista": [[l.strip()] for l in text.splitlines() if l.strip()]}
    sample = text[:4096]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
    except csv.Error:
        dialect = csv.excel
    rows = [[c.strip() for c in r] for r in csv.reader(io.StringIO(text), dialect)]
    return {"CSV": [r for r in rows if any(r)]}


# ---------------------------------------------------------------- rotas
@app.get("/")
def index():
    return send_from_directory("static", "index.html")


@app.post("/api/parse")
def parse():
    f = request.files.get("file")
    if not f:
        return jsonify(ok=False, error="Nenhum arquivo enviado."), 400
    try:
        sheets = read_table(f.filename, f.read())
    except Exception as e:  # noqa: BLE001
        return jsonify(ok=False, error=f"Não consegui ler o arquivo: {e}"), 400
    if not sheets:
        return jsonify(ok=False, error="A planilha está vazia."), 400
    return jsonify(ok=True, filename=f.filename, sheets=sheets)


@app.post("/api/test")
def test_connection():
    d = request.get_json(force=True)
    err = need(d, "account", "appKey", "appToken")
    if err:
        return err
    url = base_url(d["account"], d.get("env")) + "/api/rnb/pvt/benefits/calculatorconfiguration"
    try:
        r = requests.get(url, headers=vtex_headers(d["appKey"], d["appToken"]), timeout=30)
    except requests.RequestException as e:
        return jsonify(ok=False, error=f"Sem resposta da VTEX: {e}")
    if r.status_code < 300:
        return jsonify(ok=True, message="Conexão OK: credenciais com acesso a Promoções.")
    hints = {
        401: "AppKey/AppToken inválidos.",
        403: "Chave sem permissão no módulo de Promoções (Rates and Benefits).",
        404: "Account ou ambiente não encontrados.",
    }
    return jsonify(ok=False, error=f"HTTP {r.status_code}. {hints.get(r.status_code, r.text[:200])}")


@app.post("/api/check")
def check_existing():
    d = request.get_json(force=True)
    err = need(d, "account", "appKey", "appToken")
    if err:
        return err
    codes = d.get("codes") or []
    url = base_url(d["account"], d.get("env")) + "/api/rnb/pvt/coupon"
    try:
        r = requests.get(url, headers=vtex_headers(d["appKey"], d["appToken"]), timeout=120)
        r.raise_for_status()
        data = r.json()
    except Exception as e:  # noqa: BLE001
        return jsonify(ok=False, error=f"Não consegui listar os cupons da loja: {e}")
    if isinstance(data, dict):
        data = data.get("items") or data.get("data") or []
    existing = {}
    for c in data if isinstance(data, list) else []:
        code = str(c.get("couponCode") or "").lower()
        if code:
            existing[code] = {
                "utmSource": c.get("utmSource"),
                "utmCampaign": c.get("utmCampaign"),
                "isArchived": c.get("isArchived"),
            }
    hits = [
        {"code": code, **existing[code.lower()]}
        for code in codes
        if code.lower() in existing
    ]
    return jsonify(ok=True, totalNaLoja=len(existing), conflitos=hits)


@app.post("/api/send")
def send():
    d = request.get_json(force=True)
    err = need(d, "account", "appKey", "appToken", "utmSource")
    if err:
        return err
    codes = d.get("codes") or []
    if not codes:
        return jsonify(ok=False, error="Nenhum cupom para enviar."), 400
    job_id = uuid.uuid4().hex[:10]
    JOBS[job_id] = {
        "total": len(codes), "sent": 0, "ok": 0, "fail": 0,
        "done": False, "cancel": False, "log": [], "results": [],
        "started": time.time(),
    }
    threading.Thread(target=run_job, args=(job_id, d, codes), daemon=True).start()
    return jsonify(ok=True, jobId=job_id)


@app.get("/api/job/<job_id>")
def job_status(job_id):
    j = JOBS.get(job_id)
    if not j:
        return jsonify(ok=False, error="Job não encontrado."), 404
    since = int(request.args.get("since", 0))
    return jsonify(
        ok=True, total=j["total"], sent=j["sent"], okCount=j["ok"], fail=j["fail"],
        done=j["done"], log=j["log"][since:], logLen=len(j["log"]),
        elapsed=round(time.time() - j["started"], 1),
    )


@app.post("/api/job/<job_id>/cancel")
def job_cancel(job_id):
    j = JOBS.get(job_id)
    if j:
        j["cancel"] = True
    return jsonify(ok=True)


@app.get("/api/job/<job_id>/report.csv")
def job_report(job_id):
    j = JOBS.get(job_id)
    if not j:
        return "Job não encontrado", 404
    out = io.StringIO()
    w = csv.writer(out, delimiter=";")
    w.writerow(["cupom", "status", "detalhe"])
    w.writerows(j["results"])
    return Response(
        "﻿" + out.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename=relatorio_cupons_{job_id}.csv"},
    )


# ---------------------------------------------------------------- envio
def run_job(job_id, d, codes):
    j = JOBS[job_id]
    log = j["log"]
    url = base_url(d["account"], d.get("env")) + "/api/rnb/pvt/multiple-coupons"
    headers = vtex_headers(d["appKey"], d["appToken"])
    batch = max(1, min(int(d.get("batchSize") or 200), 500))
    utm_campaign = (d.get("utmCampaign") or "").strip() or None
    try:
        max_per_client = int(d.get("maxItemsPerClient") or 1)
    except ValueError:
        max_per_client = 1
    interval = (d.get("expirationIntervalPerUse") or "00:00:00").strip()

    def item(code):
        return {
            "quantity": 1,
            "couponConfiguration": {
                "utmSource": d["utmSource"].strip(),
                "utmCampaign": utm_campaign,
                "couponCode": code,
                "isArchived": False,
                "maxItemsPerClient": max_per_client,
                "expirationIntervalPerUse": interval,
            },
        }

    n_batches = (len(codes) + batch - 1) // batch
    log.append(f"Iniciando: {len(codes)} cupons em {n_batches} lote(s) de até {batch}.")
    for b, i in enumerate(range(0, len(codes), batch), start=1):
        if j["cancel"]:
            log.append("Envio interrompido pelo usuário.")
            for code in codes[i:]:
                j["results"].append([code, "não enviado", "cancelado"])
            break
        chunk = codes[i:i + batch]
        ok, detail = False, ""
        for attempt in range(1, 4):
            try:
                r = requests.post(url, headers=headers, json=[item(c) for c in chunk], timeout=120)
                if r.status_code < 300:
                    ok = True
                    break
                detail = f"HTTP {r.status_code}: {r.text[:300]}"
                if r.status_code not in (429, 500, 502, 503, 504):
                    break
            except requests.RequestException as e:
                detail = f"Erro de rede: {e}"
            log.append(f"Lote {b}: tentativa {attempt} falhou ({detail[:120]}). Aguardando…")
            time.sleep(4 * attempt)
        j["sent"] += len(chunk)
        if ok:
            j["ok"] += len(chunk)
            j["results"].extend([c, "criado/atualizado", ""] for c in chunk)
            log.append(f"Lote {b}/{n_batches}: OK ({len(chunk)} cupons)")
        else:
            j["fail"] += len(chunk)
            j["results"].extend([c, "erro", detail] for c in chunk)
            log.append(f"Lote {b}/{n_batches}: ERRO. {detail}")
        time.sleep(0.5)
    j["done"] = True
    log.append(f"Fim: {j['ok']} enviados com sucesso, {j['fail']} com erro.")


if __name__ == "__main__":
    url = f"http://{HOST}:{PORT}"
    print(f"\n  VTEX · Cupons em lote rodando em {url}\n  (feche esta janela para encerrar)\n")
    if not os.environ.get("NO_BROWSER"):
        threading.Timer(1.0, lambda: webbrowser.open(url)).start()
    app.run(host=HOST, port=PORT, debug=False)
