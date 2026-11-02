"""MadeiraMadeira, no navegador do monitor — só pela página de busca.

Não é VTEX (o /api/catalog_system responde 404). Medido em 01/11/2026:

  - a busca é /busca?q=<termo>; os produtos chegam depois do HTML (um proxy do
    Algolia), então só o navegador os vê. O card traz o preço à vista no Pix, o
    parcelado ("R$ 399,00 à vista no Pix ou 4x de R$ 99,75 sem juros") e, em
    alguns, o selo "FRETE GRÁTIS / SP";
  - o frete de verdade só sai na página do produto, e o cálculo passa por um
    hCaptcha. No navegador do app ele passou sozinho; no do monitor virou
    desafio na tela. Captcha não se resolve nem se contorna aqui, então o
    coletor NÃO abre a página do produto: com o selo de frete grátis para SP o
    frete é zero (o CEP de casa é de SP); sem ele, fica "não informado" — a
    oferta aparece, mas não ganha como entregue.

O robots.txt libera /busca/.
"""
from __future__ import annotations

import re
import urllib.parse

from ..base import NUM, num, oferta
from ..navegador import ir

BASE = "https://www.madeiramadeira.com.br"
LOJA = "MadeiraMadeira"
SEM_FRETE = "frete só na página do produto, atrás de verificação: confira no link"


def ler_card(t: str) -> tuple[float | None, float | None, float | None]:
    """(preço no cartão, preço no Pix, frete) do texto de um card da busca; frete None se não diz."""
    t = re.sub(r"\s+", " ", t)
    pix = num((re.search(r"R\$\s*" + NUM + r"\s*(?:\d+%\s*OFF\s*)?à vista", t, re.I) or [None, None])[1])
    m = re.search(r"(\d+)\s*x de R\$\s*" + NUM, t, re.I)
    cartao = round(int(m.group(1)) * num(m.group(2)), 2) if m else None
    frete = 0.0 if re.search(r"frete gr[áa]tis\s*(SP|Sul\s*/\s*S[ue]|Brasil)\b", t, re.I) else None
    return cartao, pix, frete


def titulo_do_card(t: str) -> str:
    """A linha do nome: a primeira que não é selo (CASHBACK), avaliação nem preço."""
    for l in (x.strip() for x in t.splitlines()):
        if len(l) > 8 and not re.search(r"cashback|ofertas|garantia|^\(\d+\)$|R\$|% OFF|à vista|sem juros", l, re.I):
            return l
    return ""


def coletar(page, cfg, produtos, data, filtros, erros):
    ofertas = []
    for prod in produtos:
        if not ir(page, f"{BASE}/busca?q={urllib.parse.quote(prod['busca'])}", espera=4):
            erros.append(f"MadeiraMadeira: busca {prod['busca']} não abriu")
            continue
        try:
            page.wait_for_selector("a[href*='index=search-web']", timeout=12000)
            cards = page.eval_on_selector_all(
                "a[href*='index=search-web']",
                "as => as.map(a => [a.href, (a.innerText || '').trim(), (a.querySelector('img') || {}).alt || ''])")
        except Exception:
            cards = []
        vistos = set()
        for href, card, alt in cards:
            url = href.split("?")[0]
            tit = alt.strip() or titulo_do_card(card)  # o alt da foto é o nome inteiro; o texto começa por selos
            if url in vistos or not tit:
                continue
            vistos.add(url)
            if not filtros(f"{tit} {url}", prod):
                continue
            cartao, pix, frete = ler_card(card)
            if not (cartao or pix):
                continue
            prazo = "frete grátis para SP (selo da busca)" if frete == 0 else SEM_FRETE
            ofertas.append(oferta(LOJA, prod["modelo"], tit, "", cartao, pix, frete, prazo, url, data))
    return ofertas
