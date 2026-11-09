"""Os pedidos da Amazon, no mesmo formato e para a mesma pousada do Mercado Livre.

Medido em 09/11/2026, e diferente do ML em tudo que importa:

  * A lista só serve para achar os pedidos (orderID no link "Exibir detalhes do pedido"); o
    TOTAL dela já inclui o frete. Tudo vem do DETALHE: "Pedido realizado 19 de outubro de 2026"
    (com ano), "Subtotal do(s) item(ns)", "Frete e manuseio" e "Total geral".
  * Item comprado é a linha seguida de "Vendido por:", e o preço é o primeiro "R$" depois dela.
    A mesma página traz recomendações com preço, mas sem "Vendido por": não entram.
  * O pedido não tem identificador por linha: com um item, item_externo = o pedido; com vários,
    "<pedido>#n" na ordem da página, senão a pousada guardaria só o primeiro.
  * Antes do "Resumo do pedido" vêm destinatário e forma de pagamento: o recorte começa nele.
  * Pedido digital (orderID "D01-…": Kindle, assinatura) tem outra página e fica de fora.

Mesma trava do ML: itens + frete têm de dar o total geral. Diferença de um item só é desconto e
sai do item; com vários, repartir seria inventar, e o pedido não sai.
"""
from __future__ import annotations

import re
from datetime import date
from decimal import Decimal
from urllib.parse import parse_qs, urlparse

from .base import RAIZ
from .compras_online import deduzir_data, fecha, linhas_de, reais, seguras

LISTA = "https://www.amazon.com.br/gp/css/order-history"
CACHE = RAIZ / "dados" / "compras-amazon.json"
LOJA = "amazon"
MAX_DETALHES = 10
_BARRADO = re.compile(r"/ap/signin|/ap/mfa|/ap/cvf|captcha|digite os caracteres", re.I)
_PRECO = re.compile(r"^R\$\s?([\d.,]+)$")


def _valor_depois(linhas: list[str], rotulo: str) -> Decimal | None:
    for k, l in enumerate(linhas[:-1]):
        if l.startswith(rotulo):
            m = _PRECO.match(linhas[k + 1])
            return reais(m.group(1)) if m else None
    return None


def pedido_do_detalhe(linhas: list[str], hoje: date) -> dict | None:
    """Data, valores e itens de uma página de detalhe; None se falta qualquer peça."""
    data_texto = next((m.group(1) for l in linhas if (m := re.match(r"^Pedido realizado (.+? de \d{4})", l))), None)
    if not data_texto or "Resumo do pedido" not in linhas:
        return None
    resumo = linhas[linhas.index("Resumo do pedido"):]
    subtotal = _valor_depois(resumo, "Subtotal do(s) item(ns)")
    frete = _valor_depois(resumo, "Frete e manuseio")
    total = _valor_depois(resumo, "Total geral")
    if subtotal is None or total is None:
        return None
    fim_total = next(k for k, l in enumerate(resumo) if l.startswith("Total geral")) + 2
    itens, ultimo = [], fim_total
    for k in range(fim_total, len(resumo)):
        if resumo[k].startswith("Vendido por") and k > 0:
            preco = next((reais(m.group(1)) for l in resumo[k + 1:k + 5] if (m := _PRECO.match(l))), None)
            if preco is None:
                return None
            itens.append({"titulo": resumo[k - 1], "valor": preco})
            ultimo = k + 5
    if not itens:
        return None
    situacao = resumo[fim_total] if fim_total < len(resumo) and resumo[fim_total] != itens[0]["titulo"] else None
    return {"data_texto": data_texto, "data": deduzir_data(data_texto, hoje), "subtotal": subtotal, "frete": frete,
            "total": total, "itens": itens, "situacao": situacao, "bloco": resumo[:ultimo]}


def _para_cache(p: dict, proibidos: list[str]) -> dict:
    return {"data_texto": p["data_texto"], "data": p["data"] and p["data"].isoformat(),
            "subtotal": str(p["subtotal"]), "frete": None if p["frete"] is None else str(p["frete"]),
            "total": str(p["total"]), "situacao": p["situacao"],
            "itens": [{"titulo": i["titulo"], "valor": str(i["valor"])} for i in p["itens"]],
            "bloco": seguras(p["bloco"], proibidos)}


def linhas_para_envio(ids: list[str], cache: dict, conta: str, proibidos: list[str]) -> tuple[list[dict], list[str]]:
    import json
    linhas, avisos = [], []
    for pedido in ids:
        p = cache.get(pedido)
        if not p or p.get("falhou"):
            continue
        frete = None if p["frete"] is None else Decimal(p["frete"])
        total = Decimal(p["total"])
        valores = [Decimal(i["valor"]) for i in p["itens"]]
        if not fecha(valores, frete, total):
            if len(valores) > 1:
                avisos.append(f"Amazon, pedido de {p['data_texto']}: itens + frete não dão o total; não enviado")
                continue
            valores = [total - (frete or 0)]  # desconto de um item só: o pago é o que sobra do frete
        varios = len(valores) > 1
        for n, (item, valor) in enumerate(zip(p["itens"], valores), 1):
            bruto = {"detalhe": seguras(p["bloco"], proibidos)}
            linhas.append({"loja": LOJA, "conta": conta, "pedido_externo": pedido,
                           "item_externo": f"{pedido}#{n}" if varios else pedido, "titulo": item["titulo"],
                           "data_pedido": p["data"], "data_texto": p["data_texto"], "valor_total": valor,
                           "frete": frete, "total_pago": total, "situacao": p.get("situacao"), "quantidade": None,
                           "url": "/gp/css/order-details", "bruto": json.dumps(bruto, ensure_ascii=False)})
    return linhas, avisos


def coletar(page, cache: dict, proibidos: list[str]) -> tuple[list[str], list[str]]:
    """Os pedidos físicos da primeira página da lista; abre só o detalhe de pedido novo."""
    from .navegador import ir, texto

    ir(page, LISTA, espera=6)
    if _BARRADO.search(page.url) or _BARRADO.search(texto(page)[:3000]):
        return [], ["Amazon pediu login ou captcha na lista de pedidos; nada lido"]
    ancoras = page.eval_on_selector_all("a", "els => els.map(e => [(e.innerText||'').trim().slice(0,50), e.href])")
    links = {}
    for t, h in ancoras:
        pedido = (parse_qs(urlparse(h).query).get("orderID") or [""])[0]
        if "detalhes do pedido" in t.lower() and re.fullmatch(r"\d{3}-\d{7}-\d{7}", pedido):
            links.setdefault(pedido, h)
    abertos, avisos = 0, []
    for pedido, h in links.items():
        if pedido in cache or abertos >= MAX_DETALHES:
            continue
        abertos += 1
        ir(page, h, espera=6)
        if _BARRADO.search(page.url) or _BARRADO.search(texto(page)[:3000]):
            avisos.append("Amazon pediu login ou captcha num detalhe; parei de abrir")
            break
        p = pedido_do_detalhe(linhas_de(texto(page)), date.today())
        cache[pedido] = _para_cache(p, proibidos) if p else {"falhou": True}
        if not p:
            avisos.append("detalhe de um pedido da Amazon não reconhecido; não volto a abri-lo")
    return list(links), avisos
