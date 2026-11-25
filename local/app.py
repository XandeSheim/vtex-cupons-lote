"""
Cupons em Lote · VTEX (versão local)

Serve a mesma interface da versão web (pasta ../public) e um proxy restrito
para a API de Promoções da VTEX, igual ao api/vtex.js usado na Vercel.

Rodar:  python app.py   ->  abre http://127.0.0.1:5000
"""
import os
import re
import threading
import webbrowser

import requests
from flask import Flask, jsonify, request, send_from_directory

HOST = "127.0.0.1"
PORT = int(os.environ.get("PORT", "5000"))
PUBLIC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "public")
BASE_URL_OVERRIDE = os.environ.get("VTEX_BASE_URL")  # só para testes

ALLOW = {
    "GET /api/rnb/pvt/benefits/calculatorconfiguration": "test",
    "GET /api/rnb/pvt/coupon": "list",
    "POST /api/rnb/pvt/multiple-coupons": "create",
    "POST /api/rnb/pvt/coupon": "upsert",
}
ENVS = {"vtexcommercestable", "vtexcommercebeta"}

app = Flask(__name__, static_folder=None)


@app.get("/")
def index():
    return send_from_directory(PUBLIC, "index.html")


@app.get("/<path:p>")
def static_files(p):
    return send_from_directory(PUBLIC, p)


@app.post("/api/vtex")
def vtex():
    b = request.get_json(force=True, silent=True) or {}
    account = str(b.get("account") or "")
    env = str(b.get("env") or "vtexcommercestable")
    app_key = str(b.get("appKey") or "").strip()
    app_token = str(b.get("appToken") or "").strip()
    method, path, body = b.get("method"), b.get("path"), b.get("body")

    kind = ALLOW.get(f"{method} {path}")
    if not kind:
        return jsonify(ok=False, error="Rota não permitida neste proxy."), 400
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{1,62}", account, re.I):
        return jsonify(ok=False, error="Account inválido."), 400
    if env not in ENVS:
        return jsonify(ok=False, error="Ambiente inválido."), 400
    if not app_key or not app_token:
        return jsonify(ok=False, error="Informe AppKey e AppToken."), 400
    if kind == "create" and (not isinstance(body, list) or not 1 <= len(body) <= 500):
        return jsonify(ok=False, error="Envie entre 1 e 500 cupons por requisição."), 400
    if kind == "upsert" and (not isinstance(body, dict) or not body.get("couponCode")):
        return jsonify(ok=False, error="Envie um cupom com couponCode."), 400

    base = BASE_URL_OVERRIDE.rstrip("/") if BASE_URL_OVERRIDE else f"https://{account}.{env}.com.br"
    try:
        r = requests.request(
            method, base + path, timeout=120,
            headers={
                "Content-Type": "application/json", "Accept": "application/json",
                "X-VTEX-API-AppKey": app_key, "X-VTEX-API-AppToken": app_token,
            },
            json=body if method == "POST" else None,
        )
    except requests.RequestException as e:
        return jsonify(ok=False, status=0, data=f"Sem resposta da VTEX: {e}")

    data = None
    if kind == "list" and r.ok:
        try:
            arr = r.json()
            if isinstance(arr, dict):
                arr = arr.get("items") or arr.get("data") or []
            data = [[str(c.get("couponCode") or ""), c.get("utmSource")] for c in arr if c.get("couponCode")]
        except ValueError:
            data = []
    elif not r.ok:
        data = r.text[:800]
    return jsonify(ok=r.ok, status=r.status_code, data=data)


if __name__ == "__main__":
    url = f"http://{HOST}:{PORT}"
    print(f"\n  Cupons em Lote rodando em {url}\n  (feche esta janela para encerrar)\n")
    if not os.environ.get("NO_BROWSER"):
        threading.Timer(1.0, lambda: webbrowser.open(url)).start()
    app.run(host=HOST, port=PORT, debug=False)
