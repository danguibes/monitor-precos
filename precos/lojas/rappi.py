"""Assaí pelo Rappi, no navegador do monitor.

O Assaí não entrega por conta própria: o site manda para iFood e Rappi. Medido em
01/11/2026: o iFood fica numa verificação antirrobô que não passa sozinha, 99Food
e Keeta são só aplicativo, e o Rappi tem site, com preço sem login.

  - qual loja Assaí atende o endereço: /lojas/tipo/supermercados lista a do
    endereço da conta (sem login, uma loja padrão da Grande São Paulo);
  - a busca: <loja>/s?term=<termo>, e os produtos vêm prontos no __NEXT_DATA__
    da página (nome, preço, apresentação "1 X 500 mL", in_stock, is_available);
  - a taxa de entrega: sem login o cabeçalho diz "Taxas / Entrega grátis (novos
    usuários)", que não vale para quem já é cliente — aí o frete fica como não
    informado. Logado (medido em 01/11/2026), o cabeçalho perde a linha "Taxas" e
    a entrega da conta vem em storeContext.charges.delivery.delivery_fee_charge,
    no __NEXT_DATA__ da loja. Logue com: py monitor.py --configurar rappi

O nome da loja traz o bairro e o cabeçalho logado traz o endereço: nada disso
sai daqui. A oferta vai como loja "Assaí", vendedor "Rappi".
"""
from __future__ import annotations

import json
import re
import urllib.parse

from ..base import NUM, num, oferta
from ..navegador import ir, texto

BASE = "https://www.rappi.com.br"
LISTA = BASE + "/lojas/tipo/supermercados"
LOJA = "Assaí"
# Taxa de serviço do Rappi, à parte da entrega. Medida em dois carrinhos de 01/11/2026
# (outra loja do Rappi, mesma conta): R$ 36,00 -> R$ 4,00 e R$ 78,00 -> R$ 8,00. Os dois
# batem com 10% arredondado ao real; dois pontos só, então vale conferir num carrinho maior.
TAXA_SERVICO = 0.10


def loja_assai(hrefs: list[str]) -> str | None:
    """A URL da loja Assaí na lista de supermercados que o Rappi mostra para o endereço."""
    for h in hrefs:
        m = re.search(r"(/lojas/\d+-assai[\w-]*)", h or "", re.I)
        if m:
            return BASE + m.group(1)
    return None


def ler_cabecalho(t: str) -> tuple[float | None, str]:
    """(taxa de entrega, prazo) do cabeçalho da loja. "Entrega grátis (novos usuários)" -> None."""
    prazo = ""
    m = re.search(r"\nEntrega\n([^\n]{1,30})\n", t)
    if m:
        prazo = m.group(1).strip()
    m = re.search(r"\nTaxas\n([^\n]+)(?:\n([^\n]+))?", t)
    if not m:
        return None, prazo
    linha, depois = m.group(1), (m.group(2) or "")
    if re.search(r"novos usu[aá]rios", linha + " " + depois, re.I):
        return None, prazo  # promoção de cliente novo: não é o frete de quem já tem conta
    v = re.search(NUM, linha)
    if v:
        return num(v.group(1)), prazo
    if re.search(r"gr[aá]tis", linha, re.I):
        return 0.0, prazo
    return None, prazo


def entrega_da_conta(t: str, dados: dict) -> float | None:
    """A entrega da conta logada, pelos dados da loja; None se o cabeçalho é o de quem não entrou."""
    if re.search(r"\nTaxas\n", t):
        return None  # cabeçalho de visitante: a promoção de cliente novo não é o frete da conta
    ctx = ((dados or {}).get("props") or {}).get("pageProps", {}).get("storeContext") or {}
    v = ((ctx.get("charges") or {}).get("delivery") or {}).get("delivery_fee_charge")
    return float(v) if isinstance(v, (int, float)) else None


def produtos_da_busca(dados: dict) -> list[dict]:
    fb = ((dados or {}).get("props") or {}).get("pageProps", {}).get("fallback") or {}
    for chave, valor in fb.items():
        if "/search/" in chave and isinstance(valor, dict):
            return valor.get("products") or []
    return []


def titulo(p: dict) -> str:
    """Nome + apresentação sem o "1 X " ("1 X 500 mL" -> "500 mL"): às vezes o volume só está nela."""
    apres = re.sub(r"^\s*1\s*[xX]\s*", "", p.get("presentation") or "").strip()
    nome = (p.get("name") or "").strip()
    return f"{nome} {apres}".strip() if apres and apres.lower() not in nome.lower() else nome


def disponivel(p: dict) -> bool:
    return str(p.get("in_stock")).lower() == "true" and str(p.get("is_available")).lower() == "true" \
        and not str(p.get("is_discontinued")).lower() == "true"


def coletar(page, cfg, produtos, data, filtros, erros):
    if not ir(page, LISTA, espera=4):
        erros.append("Assaí (Rappi): a lista de supermercados não abriu")
        return []
    hrefs = page.eval_on_selector_all("a[href*='/lojas/']", "as => as.map(a => a.getAttribute('href'))")
    loja = loja_assai(hrefs)
    if not loja:
        erros.append("Assaí (Rappi): nenhuma loja Assaí para o endereço da conta "
                     "(py monitor.py --configurar rappi para entrar e escolher o endereço)")
        return []
    if not ir(page, loja, espera=4):
        return []
    t = texto(page)
    frete, prazo = ler_cabecalho(t)
    if frete is None:
        try:
            frete = entrega_da_conta(t, json.loads(page.eval_on_selector("#__NEXT_DATA__", "e => e.textContent")))
        except Exception:
            pass
    if frete is None:
        erros.append("Assaí (Rappi): sem a taxa de entrega da sua conta (logue com py monitor.py --configurar rappi)")
    ofertas = []
    for prod in produtos:
        if not ir(page, f"{loja}/s?term={urllib.parse.quote(prod['busca'])}", espera=4):
            continue
        try:
            dados = json.loads(page.eval_on_selector("#__NEXT_DATA__", "e => e.textContent"))
            links = dict(page.eval_on_selector_all(
                "[data-qa^='product-item-']",
                "es => es.map(e => { const a = e.querySelector(\"a[href^='/p/']\");"
                " return [e.getAttribute('data-qa').replace('product-item-', ''), a ? a.getAttribute('href') : '']; })"))
        except Exception:
            erros.append(f"Assaí (Rappi): busca '{prod['busca']}' sem dados na página")
            continue
        for p in produtos_da_busca(dados):
            if not disponivel(p) or not p.get("price"):
                continue  # "Volta em breve": esgotado não vira oferta
            tit = titulo(p)
            if not filtros(tit, prod):
                continue
            preco = float(p["price"])
            link = BASE + links[str(p.get("product_id"))] if links.get(str(p.get("product_id"))) else \
                f"{loja}/s?term={urllib.parse.quote(prod['busca'])}"
            ofertas.append(oferta(LOJA, prod["modelo"], tit, "Rappi", preco, preco, frete, prazo, link, data,
                                  sku=str(p.get("product_id") or "")))
    return ofertas
