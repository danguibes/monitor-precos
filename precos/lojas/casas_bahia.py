"""Casas Bahia: verificação anti-robô no primeiro acesso, que o navegador real passa.

Busca em /{termo}/b; o CEP vai no campo de placeholder _____-___ da página do
produto, e o frete aparece no bloco "Receba em casa".
"""
from __future__ import annotations

import re

from ..base import NUM, num, oferta
from ..navegador import ir, texto


def ler_casas_bahia(t: str):
    fim = min([i for i in (t.find("Produtos Patrocinados"), t.find("Ver regras de frete")) if i > 0] or [len(t)])
    t = t[:fim]
    titulo = (re.search(r"\n([^\n]{8,})\n\n\(Cód", t) or [None, None])[1]  # a linha antes do código
    preco = num((re.search(r"por R\$\s*" + NUM, t) or [None, None])[1])
    pix = num((re.search(r"R\$\s*" + NUM + r"\s*(?:\n\s*)?no Pix", t, re.I) or [None, None])[1])
    vend = (re.search(r"Vendido e entregue por ([^\n]+)", t) or [None, None])[1]
    frete, prazo = None, ""
    ini = t.find("Receba em casa")
    if ini >= 0:
        bloco = t[ini: ini + 300]
        m = re.search(r"R\$\s*" + NUM, bloco)
        if m:
            frete = num(m.group(1))
        elif re.search(r"gr[áa]tis", bloco, re.I):
            frete = 0.0
        mp = re.search(r"(até [^\n]+)", bloco)
        prazo = mp.group(1) if mp else ""
    if preco is None and pix is None:
        return None
    return titulo, preco, pix, vend, frete, prazo


def coletar(page, cfg, produtos, data, filtros, erros, max_por_modelo=3):
    base = "https://www.casasbahia.com.br"
    cep = re.sub(r"\D", "", cfg["cep"])
    ofertas = []
    for prod in produtos:
        termo = re.sub(r"\s+", "-", prod["busca"].strip().lower())
        if not ir(page, f"{base}/{termo}/b", espera=4):
            erros.append(f"Casas Bahia: busca {prod['busca']} não abriu")
            continue
        try:
            links = page.eval_on_selector_all(
                "a[href*='/p/']", "as => as.map(a => [a.href, (a.innerText||a.title||'').trim()])")
        except Exception:
            links = []
        if not links and "protected by" in texto(page).lower():
            erros.append("Casas Bahia: bloqueio anti-robô (abra com --configurar e passe a verificação)")
            return ofertas
        vistos, cands = set(), []
        for href, tit in links:
            url = href.split("?")[0]
            if url in vistos or "patrocinado" in tit.lower():
                continue
            if filtros(f"{tit} {url}", prod):
                vistos.add(url)
                cands.append((url, tit))
        for url, tit in cands[:max_por_modelo]:
            if not ir(page, url, espera=3):
                continue
            try:
                campo = page.locator("input[placeholder='_____-___']").first
                campo.fill(cep)
                campo.press("Enter")
                page.wait_for_selector("text=Receba em casa", timeout=12000)
            except Exception:
                pass
            t_pag = texto(page)
            if prod.get("padrao") and not re.search(prod["padrao"], t_pag[:8000] + url, re.I):
                continue
            d = ler_casas_bahia(t_pag)
            if d is None:
                continue
            titulo, preco, pix, vend, frete, prazo = d
            ofertas.append(oferta("Casas Bahia", prod["modelo"], titulo or tit, vend, preco, pix,
                                  frete, prazo, url, data))
    return ofertas
