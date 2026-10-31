"""Mercado Livre: a listagem exige login no perfil do monitor; o preço vem do JSON-LD."""
from __future__ import annotations

import json
import re

from ..base import NUM, num, oferta
from ..navegador import ir, texto


def coletar(page, cfg, produtos, data, filtros, erros, max_por_modelo=4):
    ofertas = []
    for prod in produtos:
        termo = re.sub(r"\s+", "-", prod["busca"].strip().lower())
        if not ir(page, f"https://lista.mercadolivre.com.br/{termo}", espera=3):
            continue
        if "account-verification" in page.url or "login" in page.url:
            erros.append("Mercado Livre: pede login — rode 'py monitor.py --configurar' e entre na sua conta")
            return ofertas
        try:
            links = page.eval_on_selector_all(
                "a[href*='MLB']", "as => as.map(a => [a.href, (a.innerText||a.title||'').trim()])")
        except Exception:
            links = []
        vistos, cands = set(), []
        for href, tit in links:
            url = href.split("#")[0].split("?")[0]
            if url in vistos or not tit or "click1" in url:
                continue
            if filtros(tit, prod):
                vistos.add(url)
                cands.append((url, tit))
        for url, tit in cands[:max_por_modelo]:
            if not ir(page, url, espera=3):
                continue
            preco = None
            try:
                for bloco in page.eval_on_selector_all(
                        "script[type='application/ld+json']", "es => es.map(e => e.textContent)"):
                    j = json.loads(bloco)
                    ofs = (j.get("offers") if isinstance(j, dict) else None) or {}
                    if isinstance(ofs, list):
                        ofs = ofs[0] if ofs else {}
                    if ofs.get("price"):
                        preco = float(ofs["price"])
                        break
            except Exception:
                pass
            t = texto(page)
            if prod.get("padrao") and not re.search(prod["padrao"], t[:6000] + tit, re.I):
                continue
            fim = t.find("Produtos relacionados")
            t = t[:fim] if fim > 0 else t
            pix = num((re.search(r"R\$\s*" + NUM + r"\s*(?:\n\s*)?no Pix", t, re.I) or [None, None])[1])
            vend = (re.search(r"Vendido por ([^\n]+)", t) or [None, None])[1]
            frete, prazo = None, ""
            m = re.search(r"((?:Chegará|Receba|Envio|Frete)[^\n]{0,80})(?:\n[^\n]{0,80}){0,2}", t)
            if m:
                bloco = m.group(0)
                if re.search(r"gr[áa]tis", bloco, re.I):
                    frete = 0.0
                else:
                    mv = re.search(r"R\$\s*(\d{1,3}(?:\.\d{3})*(?:,\d{2})?)", bloco)
                    frete = num(mv.group(1) + ("" if "," in mv.group(1) else ",00")) if mv else None
                prazo = bloco.split("\n")[0][:60]
            if preco is None:
                continue
            ofertas.append(oferta("Mercado Livre", prod["modelo"], tit, vend, preco, pix,
                                  frete, prazo, url, data))
    return ofertas
