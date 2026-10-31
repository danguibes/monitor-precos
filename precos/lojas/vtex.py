"""Lojas na plataforma VTEX, pelas APIs públicas da própria loja (sem navegador).

  - catálogo:  /api/catalog_system/pub/products/search?ft=<termo>
  - frete:     /api/checkout/pub/orderForms/simulation  (com o CEP)

O canal de vendas (sc) varia por loja — a Consul só responde com sc=3 — e o
que funcionou fica guardado em estado.json.
"""
from __future__ import annotations

import re
import urllib.parse
from datetime import datetime

from ..base import http_json, prazo_legivel, reais
from ..filtros import eh_freezer, voltagem_ok

CANAIS_VENDA = ["1", "3", "2", "4", "5"]  # ordem de tentativa (sc)


def buscar(host: str, termo: str):
    url = (f"https://{host}/api/catalog_system/pub/products/search?"
           f"ft={urllib.parse.quote(termo)}&_from=0&_to=19")
    status, dados = http_json(url)
    if status in (200, 206) and isinstance(dados, list):
        return dados, None
    return [], f"busca '{termo}': HTTP {status}" + (f" ({dados})" if isinstance(dados, str) else "")


def simular(host: str, sc: str, sku: str, vendedor: str, cep: str):
    url = f"https://{host}/api/checkout/pub/orderForms/simulation?sc={sc}"
    corpo = {"items": [{"id": sku, "quantity": 1, "seller": vendedor}],
             "postalCode": cep, "country": "BRA"}
    status, dados = http_json(url, corpo)
    if status == 200 and isinstance(dados, dict):
        return dados
    return None


def simular_com_canal(host, sku, vendedor, cep, cache_sc: dict):
    """Descobre (e guarda) o canal de vendas (sc) que a loja usa."""
    ordem = ([cache_sc[host]] if host in cache_sc else []) + \
            [c for c in CANAIS_VENDA if c != cache_sc.get(host)]
    for sc in ordem:
        sim = simular(host, sc, sku, vendedor, cep)
        if sim and sim.get("items"):
            cache_sc[host] = sc
            return sim
        if host in cache_sc and sc == cache_sc[host]:
            # o canal conhecido respondeu vazio: item sem oferta, não insiste
            return sim
    return None


def ler_simulacao(sim: dict):
    item = sim["items"][0]
    # "available", "withoutStock", "cannotBeDelivered"...: só a primeira vira oferta.
    # Antes só se descartava item sem opção de entrega, e um sem estoque com entrega passava.
    if item.get("availability", "available") != "available":
        msgs = "; ".join(m.get("text", "") for m in sim.get("messages") or [])
        return None, msgs or f"indisponível ({item.get('availability')})"
    preco = reais(item.get("sellingPrice") or item.get("price"))
    pix = None
    for op in (sim.get("paymentData") or {}).get("installmentOptions") or []:
        if re.search(r"pix", op.get("paymentName", ""), re.I) and op.get("installments"):
            pix = reais(op["installments"][0].get("total"))
            break
    slas = []
    for li in sim.get("logisticsInfo") or []:
        for s in li.get("slas") or []:
            if s.get("deliveryChannel", "delivery") == "delivery":
                slas.append(s)
    if not slas:
        msgs = "; ".join(m.get("text", "") for m in sim.get("messages") or [])
        return None, msgs or "sem entrega para o CEP"
    melhor = min(slas, key=lambda s: s.get("price", 0))
    return {"preco": preco, "preco_pix": pix if pix and pix < (preco or 0) else preco,
            "frete": reais(melhor.get("price", 0)),
            "prazo": prazo_legivel(melhor.get("shippingEstimate"))}, None


def coletar(cfg: dict, estado: dict, produtos=None, filtro=None):
    """Sem `filtro`, vale a regra do freezer (eh_freezer + padrao + voltagem)."""
    cep = re.sub(r"\D", "", cfg["cep"])
    volt = str(cfg.get("voltagem", "127"))
    cache_sc = estado.setdefault("canal_vendas", {})
    agora = datetime.now().strftime("%Y-%m-%d %H:%M")
    ofertas, erros = [], []

    for loja in cfg["lojas"]:
        host, nome_loja = loja["host"], loja["nome"]
        falhas_busca = 0
        for prod in produtos or cfg["produtos"]:
            resultados, erro = buscar(host, prod["busca"])
            if erro:
                falhas_busca += 1
                if falhas_busca == 1:
                    erros.append(f"{nome_loja}: {erro}")
                if falhas_busca >= 2:  # loja bloqueando: pula o resto
                    erros.append(f"{nome_loja}: ignorada nesta rodada (bloqueio/erro repetido)")
                    break
                continue
            padrao = re.compile(prod["padrao"], re.I) if not filtro else None
            for p in resultados:
                nome = p.get("productName", "")
                if not filtro and not eh_freezer(nome):
                    continue
                for item in p.get("items", []):
                    texto = f"{nome} {p.get('productReference', '')} {item.get('name', '')}"
                    if filtro:
                        if not filtro(texto, prod):
                            continue
                    elif not padrao.search(texto) or not voltagem_ok(texto, volt):
                        continue
                    for vend in item.get("sellers", []):
                        oferta = vend.get("commertialOffer") or {}
                        if not oferta.get("AvailableQuantity"):
                            continue
                        sim = simular_com_canal(host, item["itemId"], vend["sellerId"], cep, cache_sc)
                        if not sim or not sim.get("items"):
                            continue
                        dados, motivo = ler_simulacao(sim)
                        if not dados:
                            continue  # vendedor não entrega no CEP
                        tot_pix = round((dados["preco_pix"] or 0) + dados["frete"], 2)
                        tot_cartao = round((dados["preco"] or 0) + dados["frete"], 2)
                        ofertas.append({
                            "data": agora, "loja": nome_loja, "modelo": prod["modelo"],
                            "produto": nome if item.get("name", "") in nome else f"{nome} — {item['name']}",
                            "sku": item["itemId"], "vendedor": vend.get("sellerName") or vend["sellerId"],
                            "preco": dados["preco"], "preco_pix": dados["preco_pix"],
                            "frete": dados["frete"], "prazo": dados["prazo"],
                            "total_pix": tot_pix, "total_cartao": tot_cartao,
                            "link": p.get("link", ""),
                        })
    # remove duplicatas (mesma loja/sku/vendedor)
    unicos = {}
    for o in ofertas:
        chave = (o["loja"], o["sku"], o["vendedor"])
        if chave not in unicos or o["total_pix"] < unicos[chave]["total_pix"]:
            unicos[chave] = o
    return list(unicos.values()), erros
