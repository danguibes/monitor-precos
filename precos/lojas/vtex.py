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


def vendedores_da_regiao(host: str, cep: str, sc: str, cache: dict) -> dict[str, str]:
    """{id: nome} das lojas físicas que atendem o CEP, pela API de regiões da VTEX (vazio se não regionaliza)."""
    if host not in cache:
        status, reg = http_json(f"https://{host}/api/checkout/pub/regions?country=BRA&postalCode={cep}&sc={sc}")
        cache[host] = {s["id"]: s.get("name") or s["id"] for s in (reg[0].get("sellers") or [])} \
            if status == 200 and isinstance(reg, list) and reg else {}
    return cache[host]


def loja_do_cep(host: str, cep: str, regiao: dict, cache: dict) -> str | None:
    """A loja física que o site usa para o CEP: a da região com o ponto mais perto.

    O site do Atacadão mostra "Entregue pela Indianópolis" e só vende por ela;
    outra loja da região com estoque não serve. Os pontos vêm com a distância
    (pickup-points) e o id começa pelo do vendedor ("atacadaobr698_...").
    """
    if len(regiao) == 1:
        return next(iter(regiao))
    if host not in cache:
        _, d = http_json(f"https://{host}/api/checkout/pub/pickup-points?postalCode={cep}&countryCode=BRA")
        pontos = sorted((d or {}).get("items", []) if isinstance(d, dict) else [],
                        key=lambda p: p.get("distance", 1e9))
        cache[host] = next((v for p in pontos for v in regiao
                            if (p.get("pickupPoint") or {}).get("id", "").startswith(v + "_")), None)
    return cache[host]


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
    cache_regiao, cache_loja, sem_loja = {}, {}, set()
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
                    vendedores = item.get("sellers", [])
                    regiao = vendedores_da_regiao(host, cep, cache_sc.get(host, "1"), cache_regiao)
                    if regiao and vendedores and all(v["sellerId"] == "1" for v in vendedores):
                        # Loja que vende pelas lojas físicas da região (Atacadão, Mambo, Oba): o
                        # vendedor "1" do catálogo diz que tem, e o site não vende por ele. Vale
                        # só a loja que o site usa para o CEP — sem estoque nela, não há oferta.
                        loja_cep = loja_do_cep(host, cep, regiao, cache_loja)
                        if not loja_cep:
                            if host not in sem_loja:
                                sem_loja.add(host)
                                erros.append(f"{nome_loja}: não identifiquei a loja física do CEP; fica sem oferta")
                            continue
                        # o nome da loja física (o bairro) não vai para a oferta: a página é pública
                        vendedores = [{"sellerId": loja_cep, "sellerName": nome_loja,
                                       "commertialOffer": {"AvailableQuantity": 1}}]
                    for vend in vendedores:
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
