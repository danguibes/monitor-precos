"""Magalu: busca pelo __NEXT_DATA__, preço e frete pelo texto da página do produto."""
from __future__ import annotations

import json
import re
import time

from ..base import NUM, num, oferta
from ..navegador import ir, texto


def _produtos(page):
    """Lê a lista de produtos do __NEXT_DATA__ da página de busca."""
    try:
        bruto = page.eval_on_selector("#__NEXT_DATA__", "e => e.textContent")
        dados = json.loads(bruto)
    except Exception:
        return []
    achados = []

    def andar(o, prof=0):
        if prof > 14:
            return
        if isinstance(o, dict):
            if o.get("type") == "product" and o.get("title") and o.get("path"):
                achados.append({"titulo": o["title"], "path": o["path"]})
                return
            for v in o.values():
                andar(v, prof + 1)
        elif isinstance(o, list):
            for v in o:
                andar(v, prof + 1)

    andar(dados)
    vistos, unicos = set(), []
    for a in achados:
        if a["path"] not in vistos:
            vistos.add(a["path"])
            unicos.append(a)
    return unicos


def _garante_cep(page, cep_fmt: str):
    t = texto(page)
    if cep_fmt in t:
        return True
    try:
        page.get_by_role("button", name=re.compile("Alterar o CEP|Informe seu CEP|CEP", re.I)).first.click()
        campo = page.get_by_placeholder("CEP").first
        campo.fill(re.sub(r"\D", "", cep_fmt))
        campo.press("Enter")
        time.sleep(3)
        return cep_fmt in texto(page)
    except Exception:
        return False


def ler_magalu(t: str):
    fim = t.find("Quem viu este produto")
    t = t[:fim] if fim > 0 else t
    pix = num((re.search(r"R\$\s*" + NUM + r"\s*\n+\s*no Pix", t, re.I) or [None, None])[1])
    cartao = num((re.search(r"Ou R\$\s*" + NUM + r" em", t) or [None, None])[1])
    vend = (re.search(r"Vendido (?:e entregue )?por ([^\n]+)", t) or [None, None])[1]
    frete, prazo = None, ""
    ini = t.find("Enviar para")
    if ini >= 0:
        bloco = t[ini: ini + 400]
        m = re.search(r"R\$\s*" + NUM, bloco)
        if m:
            frete = num(m.group(1))
        elif re.search(r"gr[áa]tis", bloco, re.I):
            frete = 0.0
        mp = re.search(r"Receba (até [^\n]+)", bloco)
        prazo = mp.group(1) if mp else ""
    if pix is None and cartao is None:
        return None
    return pix, cartao, vend, frete, prazo


def coletar(page, cfg, produtos, data, filtros, erros, max_por_modelo=3):
    base = "https://www.magazineluiza.com.br"
    cep_fmt = cfg["cep"]
    ofertas, cep_ok = [], False
    for prod in produtos:
        if not ir(page, f"{base}/busca/{prod['busca'].replace(' ', '+')}/"):
            erros.append(f"Magalu: busca {prod['busca']} não abriu")
            continue
        candidatos = [c for c in _produtos(page) if filtros(c["titulo"], prod)][:max_por_modelo]
        for c in candidatos:
            if not ir(page, base + c["path"], espera=3):
                continue
            if not cep_ok:
                cep_ok = _garante_cep(page, cep_fmt)
                if not cep_ok:
                    erros.append("Magalu: não consegui fixar o CEP (rode --configurar)")
                    return ofertas
            t_pag = texto(page)
            if prod.get("padrao") and not re.search(prod["padrao"], t_pag[:6000], re.I):
                continue  # página não é do modelo buscado
            d = ler_magalu(t_pag)
            if d is None:
                continue  # indisponível
            pix, cartao, vend, frete, prazo = d
            ofertas.append(oferta("Magalu", prod["modelo"], c["titulo"], vend, cartao, pix,
                                  frete, prazo, base + c["path"], data))
    return ofertas
