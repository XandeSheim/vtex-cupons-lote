// Proxy restrito para a API de Promoções da VTEX.
// A API privada da VTEX não aceita chamadas diretas do navegador (CORS),
// então a página chama /api/vtex e esta função repassa para a loja.
// Só quatro rotas são permitidas, e nada é gravado: as credenciais vêm em cada requisição.

const ALLOW = {
  "GET /api/rnb/pvt/benefits/calculatorconfiguration": "test",
  "GET /api/rnb/pvt/coupon": "list",
  "POST /api/rnb/pvt/multiple-coupons": "create",
  "POST /api/rnb/pvt/coupon": "upsert",
};
const ENVS = ["vtexcommercestable", "vtexcommercebeta"];

function baseUrl(account, env) {
  if (process.env.VTEX_BASE_URL) return process.env.VTEX_BASE_URL.replace(/\/$/, "");
  return `https://${account}.${env}.com.br`;
}

module.exports = async (req, res) => {
  res.setHeader("Cache-Control", "no-store");
  if (req.method !== "POST") return res.status(405).json({ ok: false, error: "Use POST." });

  let b = req.body;
  if (typeof b === "string") { try { b = JSON.parse(b || "{}"); } catch { b = {}; } }
  const { account = "", env = "vtexcommercestable", appKey = "", appToken = "", method = "", path = "", body } = b || {};

  const kind = ALLOW[`${method} ${path}`];
  if (!kind) return res.status(400).json({ ok: false, error: "Rota não permitida neste proxy." });
  if (!/^[a-z0-9][a-z0-9-]{1,62}$/i.test(account)) return res.status(400).json({ ok: false, error: "Account inválido." });
  if (!ENVS.includes(env)) return res.status(400).json({ ok: false, error: "Ambiente inválido." });
  if (!appKey.trim() || !appToken.trim()) return res.status(400).json({ ok: false, error: "Informe AppKey e AppToken." });
  if (kind === "create" && (!Array.isArray(body) || body.length < 1 || body.length > 500))
    return res.status(400).json({ ok: false, error: "Envie entre 1 e 500 cupons por requisição." });
  if (kind === "upsert" && (!body || typeof body !== "object" || Array.isArray(body) || !body.couponCode))
    return res.status(400).json({ ok: false, error: "Envie um cupom com couponCode." });

  try {
    const r = await fetch(baseUrl(account, env) + path, {
      method,
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
        "X-VTEX-API-AppKey": appKey.trim(),
        "X-VTEX-API-AppToken": appToken.trim(),
      },
      body: method === "POST" ? JSON.stringify(body) : undefined,
    });
    const text = await r.text();
    let data = null;
    if (kind === "list" && r.ok) {
      // devolve só código e UTM para caber no limite de resposta
      try {
        let arr = JSON.parse(text);
        if (!Array.isArray(arr)) arr = arr.items || arr.data || [];
        data = arr.map((c) => [String(c.couponCode || ""), c.utmSource || null]).filter((c) => c[0]);
      } catch { data = []; }
    } else if (!r.ok) {
      data = text.slice(0, 800);
    }
    const retryAfter = parseInt(r.headers.get("retry-after") || "", 10) || null;
    return res.status(200).json({ ok: r.ok, status: r.status, data, retryAfter });
  } catch (e) {
    return res.status(200).json({ ok: false, status: 0, data: "Sem resposta da VTEX: " + (e.message || e) });
  }
};
