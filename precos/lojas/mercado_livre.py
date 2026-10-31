"""Mercado Livre: a listagem exige login no perfil do monitor.

Preço e frete vêm do JSON-LD da página do produto: `offers.price` é o preço
da caixa de compra (no Pix) e `offers.shippingDetails.shippingRate.value` é o
frete para o endereço da conta logada. O texto da página só completa o que o
JSON-LD não tem — preço no cartão, vendedor e prazo —, e sempre recortado na
caixa de compra: a página lista outros anúncios ("Produtos relacionados"), e
ler o frete do texto inteiro pegava o "Frete grátis" deles.
"""
from __future__ import annotations

import json
import re

from ..base import num, oferta
from ..navegador import ir, texto


def ler_jsonld(blocos: list[str]):
    """{"preco", "frete", "dias"} da oferta principal, ou None."""
    for bloco in blocos:
        try:
            j = json.loads(bloco)
        except ValueError:
            continue
        ofs = (j.get("offers") if isinstance(j, dict) else None) or {}
        if isinstance(ofs, list):
            ofs = ofs[0] if ofs else {}
        if not ofs.get("price"):
            continue
        if not str(ofs.get("availability", "InStock")).endswith("InStock"):
            return None  # OutOfStock, SoldOut...: a página mostra preço, mas não vende
        envio = ofs.get("shippingDetails") or {}
        if isinstance(envio, list):
            envio = envio[0] if envio else {}
        taxa = (envio.get("shippingRate") or {}).get("value")
        tempo = envio.get("deliveryTime") or {}
        dias = [(tempo.get(k) or {}).get("maxValue") for k in ("handlingTime", "transitTime")]
        return {"preco": float(ofs["price"]),
                "frete": float(taxa) if taxa is not None else None,
                "dias": sum(d for d in dias if d) or None}
    return None


def ler_caixa(t: str):
    """(preço no cartão, vendedor, prazo, frete grátis?) da caixa de compra do texto da página."""
    # Âncora: o link de entrega fica dentro da caixa nos dois layouts — o de
    # eletro ("Comprar agora") e o de mercado, que só tem "Adicionar ao carrinho".
    ancora = t.find("Mais detalhes e formas de entrega")
    if ancora < 0:
        ancora = t.find("Comprar agora")
    if ancora < 0:
        return None, None, "", False
    i_pix = t.rfind("no Pix", max(0, ancora - 900), ancora)
    caixa = t[i_pix if i_pix >= 0 else max(0, ancora - 300): ancora]
    plano = re.sub(r"\s+", " ", caixa)
    mc = re.search(r"ou R\$ ?([\d.]+)(?: ?, ?(\d{2}))? em \d+x", plano)
    cartao = num(f"{mc.group(1)},{mc.group(2) or '00'}") if mc else None
    prazos = re.findall(r"((?:Chegará|Receba|Chega)[^\n]*)", caixa)
    prazo = prazos[-1].strip() if prazos else ""  # o último antes do link é o da caixa
    gratis = bool(re.search(r"(Frete|Chegará|Chega|Envio) gr[áa]tis", prazo or caixa[-200:], re.I))
    mv = re.search(r"(?:Loja oficial|Vendido por)\s*\n\s*([^\n]+)", t[ancora: ancora + 900])
    return cartao, (mv.group(1).strip() if mv else None), prazo, gratis


def coletar(page, cfg, produtos, data, filtros, erros, max_por_modelo=4):
    ofertas = []
    for prod in produtos:
        termo = re.sub(r"\s+", "-", prod["busca"].strip().lower())
        if not ir(page, f"https://lista.mercadolivre.com.br/{termo}", espera=3):
            continue
        if "captcha" in page.url:  # o monitor não contorna captcha: avisa e para
            erros.append("Mercado Livre: pediu captcha (excesso de acessos?) — rode 'py monitor.py --configurar "
                         "mercadolivre' e resolva na janela; até lá a loja fica sem ofertas")
            return ofertas
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
            try:
                blocos = page.eval_on_selector_all(
                    "script[type='application/ld+json']", "es => es.map(e => e.textContent)")
            except Exception:
                blocos = []
            ld = ler_jsonld(blocos)
            if ld is None:
                continue
            t = texto(page)
            if prod.get("padrao") and not re.search(prod["padrao"], t[:6000] + tit, re.I):
                continue
            cartao, vend, prazo, gratis = ler_caixa(t)
            frete = ld["frete"] if ld["frete"] is not None else (0.0 if gratis else None)
            if not prazo and ld["dias"]:
                prazo = f"até {ld['dias']} dias"
            ofertas.append(oferta("Mercado Livre", prod["modelo"], tit, vend, cartao or ld["preco"],
                                  ld["preco"], frete, prazo, url, data))
    return ofertas
