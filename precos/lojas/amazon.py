"""Amazon (amazon.com.br): pela busca, no navegador do monitor.

Sem login, a Amazon chuta o CEP pela localização da internet — e o frete da
busca é para esse CEP. Por isso o coletor confere o CEP do cabeçalho e, se não
for o de local.toml, troca pelo "Atualizar CEP" da própria página (fica salvo
no perfil do monitor).

Cada card da busca traz tudo: título (no h2), o preço grande — que é o do Pix,
com desconto —, o preço normal antes de "à vista no Pix…", e a linha de
entrega para o CEP. Frete grátis condicional ("no seu primeiro pedido", "com o
Prime") NÃO vale como frete zero: vira frete não informado, que não ganha o
card de melhor oferta.
"""
from __future__ import annotations

import re
import time
import urllib.parse

from ..base import NUM, num, oferta
from ..navegador import ir

BASE = "https://www.amazon.com.br"
_PRECO = re.compile(r"^R\$\s*" + NUM + r"$")
CONDICIONAL = re.compile(r"primeiro pedido|prime|qualificados", re.I)


def ler_card(titulo: str, texto: str):
    """{"pix", "cartao", "frete", "prazo"} de um card da busca, ou None se não está à venda."""
    if re.search(r"indispon[íi]vel|n[ãa]o dispon[íi]vel", texto, re.I):
        return None
    linhas = [l.strip() for l in texto.split("\n")]
    precos = [(i, num(m.group(1))) for i, l in enumerate(linhas) if (m := _PRECO.match(l))
              and not (i and linhas[i - 1].rstrip().endswith(("De:", "(")))]  # preço antigo e preço por unidade
    if not precos:
        return None
    pix = precos[0][1]
    cartao = pix
    # O preço do cartão é o que a linha do Pix diz — "R$ Y no cartão" ou "em até Nx de R$ Z".
    # O segundo preço solto do card é o de tabela, riscado: R$ 2.299 num freezer cujo
    # cartão era 12 × 148,05 = 1.776,60.
    i_pix = next((i for i, l in enumerate(linhas) if "à vista no Pix" in l), None)
    if i_pix is not None:
        trecho = " ".join(linhas[i_pix:i_pix + 3])
        m = re.search(r"R\$\s*" + NUM + r"\s*no cart", trecho)
        mp = re.search(r"em até (\d+)x de\s*R\$\s*" + NUM, trecho)
        if m:
            cartao = num(m.group(1))
        elif mp:
            cartao = round(int(mp.group(1)) * num(mp.group(2)), 2)
    frete, prazo = None, ""
    for l in linhas:
        if not l.startswith("Entrega"):
            continue
        if CONDICIONAL.search(l):
            prazo = prazo or l.split(":", 1)[-1].strip()
            continue  # grátis só em condição: não é o frete de quem compra normalmente
        m = re.match(r"Entrega\s+(GR[ÁA]TIS|R\$\s*" + NUM + r")\s*:?\s*(.*)", l, re.I)
        if m:
            frete = 0.0 if m.group(1).upper().startswith("GR") else num(m.group(2))
            prazo = m.group(3).strip()
            break
    return {"pix": pix, "cartao": max(cartao, pix), "frete": frete, "prazo": prazo}


def _cep_do_cabecalho(page) -> str:
    try:
        return re.sub(r"\D", "", page.locator("#glow-ingress-line2, #nav-global-location-popover-link")
                      .first.inner_text(timeout=5000))
    except Exception:
        return ""


def garantir_cep(page, cep: str) -> bool:
    """Põe o CEP de local.toml no cabeçalho, pelo "Atualizar CEP" da página."""
    if cep in _cep_do_cabecalho(page):
        return True
    try:
        page.locator("#nav-global-location-popover-link").first.click(timeout=8000)
        time.sleep(2)
        campos = page.locator("input[id^='GLUXZipUpdateInput']")
        if campos.count() == 2:
            campos.nth(0).fill(cep[:5])
            campos.nth(1).fill(cep[5:])
        else:
            campos.first.fill(cep)
        page.locator("#GLUXZipUpdate input, #GLUXZipUpdate").first.click(timeout=8000)
        time.sleep(3)
        for sel in ("button[name='glowDoneButton']", "#GLUXConfirmClose", ".a-popover-footer input"):
            try:
                page.locator(sel).first.click(timeout=2000)
                break
            except Exception:
                pass
        time.sleep(2)
        page.reload(wait_until="domcontentloaded")
        time.sleep(2)
    except Exception:
        return False
    return cep in _cep_do_cabecalho(page)


def coletar(page, cfg, produtos, data, filtros, erros, max_por_busca=20):
    cep = re.sub(r"\D", "", cfg["cep"])
    if not ir(page, BASE + "/", espera=3):
        erros.append("Amazon: não abriu a página")
        return []
    if not garantir_cep(page, cep):
        erros.append("Amazon: não consegui pôr o CEP no cabeçalho — sem ele o frete seria de outro lugar")
        return []
    ofertas = []
    for prod in produtos:
        if not ir(page, f"{BASE}/s?k={urllib.parse.quote_plus(prod['busca'])}", espera=3):
            erros.append(f"Amazon: busca {prod['busca']} não abriu")
            continue
        if "captcha" in page.url.lower() or page.locator("form[action*='validateCaptcha']").count():
            erros.append("Amazon: pediu captcha — rode 'py monitor.py --configurar amazon' e resolva na janela")
            return ofertas
        cards = page.locator("[data-component-type='s-search-result']")
        for k in range(min(max_por_busca, cards.count())):
            c = cards.nth(k)
            try:
                titulo = c.locator("h2").first.inner_text(timeout=3000).strip()
                texto_card = c.inner_text(timeout=3000)
                asin = c.get_attribute("data-asin") or ""
            except Exception:
                continue
            if not asin or not filtros(titulo, prod):
                continue
            d = ler_card(titulo, texto_card)
            if d is None:
                continue
            ofertas.append(oferta("Amazon", prod["modelo"], titulo, "", d["cartao"], d["pix"],
                                  d["frete"], d["prazo"], f"{BASE}/dp/{asin}", data, sku=asin))
    return ofertas
