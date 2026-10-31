"""Pão de Açúcar: API própria do GPA (api.vendas.gpa.digital), sem navegador.

  - entrega:  GET  /pa/delivery-v2/ecom/deliveryOptions?zipCode=<cep>
              -> as lojas que atendem o CEP, cada uma com a taxa de entrega
  - busca:    POST /pa/search/search  {terms, storeId, ...}
              -> o preço é o da loja escolhida

Não há desconto no Pix. O pedido mínimo do site não aparece em nenhuma das duas.
"""
from __future__ import annotations

import re

from ..base import http_json, oferta

API = "https://api.vendas.gpa.digital/pa"


def ler_entrega(dados: dict):
    """Escolhe a loja Pão de Açúcar (não Minuto nem Hub) com a entrega mais barata.

    Retorna {"loja_id", "loja", "frete", "prazo"} ou None.
    """
    opcoes = [o for o in (dados or {}).get("deliveryTypes") or []
              if (o.get("storeType") or "").strip().lower() == "pão de açúcar"]
    if not opcoes:
        return None
    o = min(opcoes, key=lambda o: float(o.get("price") or 0))
    prazo = f'{o.get("day", "")} {o.get("ini", "")}–{o.get("end", "")}'.strip(" –")
    return {"loja_id": o["storeid"], "loja": o.get("storeName", ""),
            "frete": round(float(o.get("price") or 0), 2), "prazo": prazo}


def ler_busca(dados: dict):
    """[(nome, preço, sku, link)] dos produtos em estoque."""
    res = []
    for p in (dados or {}).get("products") or []:
        if p.get("stock") and p.get("price") and p.get("name"):
            res.append((p["name"], round(float(p["price"]), 2), str(p.get("sku") or p.get("id", "")),
                        p.get("urlDetails", "")))
    return res


def buscar(termo: str, loja_id):
    corpo = {"terms": termo, "page": 1, "sortBy": "relevance", "resultsPerPage": 36,
             "allowRedirect": True, "storeId": loja_id, "department": "ecom",
             "customerPlus": True, "partner": "fallback"}
    status, dados = http_json(f"{API}/search/search", corpo)
    if status == 404:  # é como a API diz "nenhum resultado"
        return {"products": []}, None
    return (dados, None) if status == 200 and isinstance(dados, dict) else (None, f"busca '{termo}': HTTP {status}")


def coletar(cfg, produtos, data, filtros, erros):
    cep = re.sub(r"\D", "", cfg["cep"])
    status, dados = http_json(f"{API}/delivery-v2/ecom/deliveryOptions?zipCode={cep}")
    entrega = ler_entrega(dados) if status == 200 else None
    if not entrega:
        erros.append(f"Pão de Açúcar: nenhuma loja entrega no CEP (HTTP {status})")
        return []
    ofertas = []
    for prod in produtos:
        dados, erro = buscar(prod["busca"], entrega["loja_id"])
        if erro:
            erros.append(f"Pão de Açúcar: {erro}")
            continue
        for nome, preco, sku, link in ler_busca(dados):
            if filtros(nome, prod):
                # o nome da loja que atende o CEP não vai para a oferta: o relatório é publicado
                ofertas.append(oferta("Pão de Açúcar", prod["modelo"], nome, "Pão de Açúcar", preco, None,
                                      entrega["frete"], entrega["prazo"], link, data, sku))
    return ofertas
