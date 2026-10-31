"""Shopee pelo site: desligada, porque o site barra o navegador automatizado com captcha.

Não se contorna o captcha. O caminho previsto é a API oficial de afiliados,
com as credenciais num .env local (fora do git).
"""
from __future__ import annotations

import time

from ..base import oferta


def coletar(page, cfg, produtos, data, filtros, erros, max_por_modelo=5):
    ofertas = []
    capturas = []

    def ouvir(resp):
        if "search_items" in resp.url:
            try:
                capturas.append(resp.json())
            except Exception:
                pass

    page.on("response", ouvir)
    try:
        for prod in produtos:
            capturas.clear()
            try:
                with page.expect_response(lambda r: "search_items" in r.url, timeout=20000):
                    page.goto("https://shopee.com.br/search?keyword=" + prod["busca"],
                              wait_until="domcontentloaded", timeout=45000)
                time.sleep(1.5)
            except Exception:
                pass
            if "verify" in page.url or "login" in page.url:
                erros.append("Shopee: pede login — rode 'py monitor.py --configurar' e entre na sua conta")
                return ofertas
            itens = []
            for c in capturas:
                for it in (c.get("items") or []):
                    b = it.get("item_basic") or it
                    if b.get("name"):
                        itens.append(b)
            n = 0
            for b in itens:
                if not filtros(b["name"], prod):
                    continue
                preco = (b.get("price") or 0) / 100000 or None
                link = f"https://shopee.com.br/product/{b.get('shopid')}/{b.get('itemid')}"
                ofertas.append(oferta("Shopee", prod["modelo"], b["name"], b.get("shop_name") or "",
                                      preco, None, None, "", link, data, str(b.get("itemid", ""))))
                n += 1
                if n >= max_por_modelo:
                    break
    finally:
        page.remove_listener("response", ouvir)
    return ofertas
