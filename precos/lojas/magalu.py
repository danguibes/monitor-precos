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
    vend = (re.search(r"Vendido (?:e entregue )?por ([^\n]+?)(?: e entregue por [^\n]+)?\n", t) or [None, None])[1]
    if pix is None and cartao is None:
        return None
    frete, prazo = ler_frete(t, max(pix or 0, cartao or 0))
    return pix, cartao, vend, frete, prazo


def ler_frete(t: str, preco: float):
    """(frete, prazo) do bloco de entrega do produto, ou (None, "") se não deu.

    Há dois "Enviar para" na página: o da barra do topo e o do produto. O do
    produto é o último antes de "Adicionar à sacola", e a taxa é o R$ que fecha
    esse bloco ("Receba até ... / R$ 49,90 / Adicionar à sacola"). Ler a partir
    do primeiro era o defeito: os 400 caracteres depois da barra do topo já
    alcançavam o preço do produto, que era gravado como frete.
    """
    fim = t.find("Adicionar à sacola")
    ini = t.rfind("Enviar para", 0, fim) if fim > 0 else -1
    if ini < 0:
        return None, ""
    bloco = t[ini:fim]
    mp = re.search(r"(Receba [^\n]+)", bloco)
    prazo = mp.group(1).replace("Receba ", "") if mp else ""
    if "calcular o frete" in bloco:  # "Não foi possível calcular o frete. Tente novamente."
        return None, ""
    valores = re.findall(r"R\$\s*" + NUM, bloco)
    if valores:
        frete = num(valores[-1])
        # trava: frete do tamanho do produto é leitura errada, não frete
        return (frete, prazo) if not preco or frete < preco * 0.5 else (None, "")
    if re.search(r"gr[áa]tis", bloco, re.I):
        return 0.0, prazo
    return None, prazo


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
            if "calcular o frete" in t_pag:  # falha intermitente da página: o próprio link dela refaz
                try:
                    page.get_by_text("Tente novamente").first.click(timeout=5000)
                    page.wait_for_selector("text=Receba", timeout=10000)
                    t_pag = texto(page)
                except Exception:
                    pass  # segue sem frete: a oferta fica "frete não informado"
            if prod.get("padrao") and not re.search(prod["padrao"], t_pag[:6000], re.I):
                continue  # página não é do modelo buscado
            d = ler_magalu(t_pag)
            if d is None:
                continue  # indisponível
            pix, cartao, vend, frete, prazo = d
            ofertas.append(oferta("Magalu", prod["modelo"], c["titulo"], vend, cartao, pix,
                                  frete, prazo, base + c["path"], data))
    return ofertas
