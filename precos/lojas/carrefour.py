"""Carrefour: VTEX, mas o catalog_system devolve 403.

A busca inteligente e a simulação de frete funcionam quando chamadas de
dentro da página, num navegador real.
"""
from __future__ import annotations

import re

from ..base import oferta
from ..navegador import ir
from .vtex import ler_simulacao

JS_VTEX_BUSCA = """async (termo) => {
  const u = '/_v/api/intelligent-search/product_search/?query=' + encodeURIComponent(termo) + '&count=20&page=1&locale=pt-BR';
  const r = await fetch(u); if (!r.ok) return {erro: 'HTTP ' + r.status};
  return {produtos: (await r.json()).products || []};
}"""
JS_VTEX_SIM = """async ([sku, seller, cep, sc]) => {
  const r = await fetch('/api/checkout/pub/orderForms/simulation?sc=' + sc, {method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({items: [{id: sku, quantity: 1, seller}], postalCode: cep, country: 'BRA'})});
  return r.ok ? await r.json() : null;
}"""


def coletar(page, cfg, produtos, data, filtros, erros):
    host = "https://www.carrefour.com.br"
    cep = re.sub(r"\D", "", cfg["cep"])
    ofertas = []
    if not ir(page, host + "/"):
        erros.append("Carrefour: não abriu a página")
        return ofertas
    for prod in produtos:
        res = page.evaluate(JS_VTEX_BUSCA, prod["busca"])
        if res.get("erro"):
            erros.append(f"Carrefour: busca {prod['busca']}: {res['erro']}")
            continue
        for p in res["produtos"]:
            nome = p.get("productName", "")
            for item in p.get("items", []):
                txt = f"{nome} {p.get('productReference', '')} {item.get('name', '')}"
                if not filtros(txt, prod):
                    continue
                for v in item.get("sellers", []):
                    if not (v.get("commertialOffer") or {}).get("AvailableQuantity"):
                        continue
                    sim = page.evaluate(JS_VTEX_SIM, [item["itemId"], v["sellerId"], cep, "1"])
                    if not sim or not sim.get("items"):
                        continue
                    d, _ = ler_simulacao(sim)
                    if not d:
                        continue
                    lk = p.get("link") or ""
                    link = (lk if lk.startswith("http") else host + lk) if lk else \
                        host + "/" + (p.get("linkText") or "") + "/p"
                    ofertas.append(oferta("Carrefour", prod["modelo"], nome, v.get("sellerName"),
                                          d["preco"], d["preco_pix"], d["frete"], d["prazo"],
                                          link, data, item["itemId"]))
    return ofertas
