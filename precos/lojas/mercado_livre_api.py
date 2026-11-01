"""Mercado Livre pela API oficial: catálogo, anúncios e frete para o CEP, sem navegador.

Medido com o app próprio em 01/11/2026 (ferramentas/sonda_api_meli.py):

  - /sites/MLB/search (a busca aberta) e /items/{id} dão 403, mesmo com token;
  - /products/search e /products/{id}/items respondem COM o token do app;
  - /items/{id}/shipping_options?zip_code= responde SEM token — e dá 403 COM ele;
  - /users/{id} (o nome do vendedor) só responde com token.

Só alcança produto de CATÁLOGO (o que o Mercado Livre unificou numa ficha com
marca e modelo), e por isso vale para os monitores de marca: `mercado_livre = "api"`
no .toml. Anúncio avulso, fora do catálogo, fica de fora — nos outros monitores
o navegador continua. Sem credenciais ou com o token recusado, quem chama volta
para o navegador.

Credenciais em local.toml, [mercadolivre] client_id e client_secret (fora do git).
O token do app vem com escopo de escrita na conta: nunca é gravado nem impresso.
"""
from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request

from ..base import UA, oferta

API = "https://api.mercadolibre.com"
LOJA = "Mercado Livre"
PAUSA = 0.4


class SemAcesso(Exception):
    """Sem credenciais, ou o token do app foi recusado: a loja volta para o navegador."""


def _pedir(caminho: str, token: str | None = None, form: dict | None = None, _de_novo=True):
    """429 ("muitas requisições", visto em 01/11 depois de uma noite de testes): espera e tenta uma vez mais."""
    st, d = _pedir_uma(caminho, token, form)
    if st == 429 and _de_novo:
        time.sleep(10)
        return _pedir(caminho, token, form, _de_novo=False)
    return st, d


def _pedir_uma(caminho: str, token: str | None = None, form: dict | None = None):
    req = urllib.request.Request(API + caminho, data=urllib.parse.urlencode(form).encode() if form else None,
                                 headers={"Accept": "application/json", "User-Agent": UA,
                                          **({"Authorization": f"Bearer {token}"} if token else {})})
    try:
        with urllib.request.urlopen(req, timeout=25) as r:
            return r.status, json.loads(r.read().decode("utf-8") or "null")
    except urllib.error.HTTPError as e:
        return e.code, None
    except (urllib.error.URLError, TimeoutError, ValueError, OSError):
        return 0, None
    finally:
        time.sleep(PAUSA)


def credenciais() -> dict | None:
    from ..monitores import LOCAL, ler_toml
    ml = ler_toml(LOCAL, obrigatorio=False).get("mercadolivre") or {}
    return ml if ml.get("client_id") and ml.get("client_secret") else None


def pedir_token(ml: dict | None) -> str:
    if not ml:
        raise SemAcesso("sem [mercadolivre] no local.toml")
    st, d = _pedir("/oauth/token", form={"grant_type": "client_credentials",
                                         "client_id": ml["client_id"], "client_secret": ml["client_secret"]})
    if st != 200 or not isinstance(d, dict) or not d.get("access_token"):
        raise SemAcesso(f"token do app recusado (HTTP {st})")
    return d["access_token"]


def ler_frete(dados) -> tuple[float | None, str]:
    """(o frete mais barato, "até dd/mm"), ou (None, "") se não veio opção."""
    opcoes = [o for o in (dados or {}).get("options") or [] if o.get("cost") is not None]
    if not opcoes:
        return None, ""
    o = min(opcoes, key=lambda o: (o["cost"], (o.get("estimated_delivery_time") or {}).get("date") or ""))
    data = ((o.get("estimated_delivery_time") or {}).get("date") or "")[:10]
    prazo = f"até {data[8:10]}/{data[5:7]}" if re.fullmatch(r"\d{4}-\d\d-\d\d", data) else ""
    return round(float(o["cost"]), 2), prazo


def link_do_anuncio(item_id: str) -> str:
    """MLB6037965678 -> https://produto.mercadolivre.com.br/MLB-6037965678 (o anúncio daquele preço)."""
    m = re.fullmatch(r"([A-Z]{3})(\d+)", item_id or "")
    return f"https://produto.mercadolivre.com.br/{m.group(1)}-{m.group(2)}" if m else ""


def coletar(cfg, produtos, data, filtro, erros, ml=None, max_produtos=10, max_anuncios=2):
    """Para cada busca: produtos do catálogo que passam no filtro do monitor, os anúncios
    novos mais baratos de cada um, e o frete de cada anúncio para o CEP."""
    token = pedir_token(ml if ml is not None else credenciais())
    cep = re.sub(r"\D", "", cfg.get("cep", ""))
    vendedores: dict = {}

    def vendedor(seller_id):
        if seller_id not in vendedores:
            st, u = _pedir(f"/users/{seller_id}", token)
            vendedores[seller_id] = (u or {}).get("nickname", "") if st == 200 and isinstance(u, dict) else ""
        return vendedores[seller_id]

    ofertas, sem_frete = [], 0
    for prod in produtos:
        st, cat = _pedir("/products/search?status=active&site_id=MLB&limit=50&q="
                         + urllib.parse.quote(prod["busca"]), token)
        if st in (401, 403):
            raise SemAcesso(f"catálogo recusado (HTTP {st})")
        if st != 200 or not isinstance(cat, dict):
            erros.append(f"Mercado Livre (API): busca '{prod['busca']}' falhou (HTTP {st})")
            continue
        cands = [p for p in cat.get("results") or [] if p.get("name") and filtro(p["name"], prod)]
        for p in cands[:max_produtos]:
            st, its = _pedir(f"/products/{p['id']}/items", token)
            if st != 200 or not isinstance(its, dict):
                continue  # 404 "No winners found": produto sem anúncio vendendo agora
            novos = sorted((i for i in its.get("results") or []
                            if i.get("condition") == "new" and i.get("currency_id") == "BRL" and i.get("price")),
                           key=lambda i: i["price"])
            for i in novos[:max_anuncios]:
                # sem token: com ele, o frete dá 403 (medido em 01/11)
                st, fr = _pedir(f"/items/{i['item_id']}/shipping_options?zip_code={cep}")
                frete, prazo = ler_frete(fr) if st == 200 else (None, "")
                sem_frete += frete is None
                ofertas.append(oferta(LOJA, prod["modelo"], p["name"], vendedor(i.get("seller_id")),
                                      float(i["price"]), float(i["price"]), frete, prazo,
                                      link_do_anuncio(i["item_id"]), data, sku=i["item_id"]))
    if sem_frete:
        erros.append(f"Mercado Livre (API): {sem_frete} anúncio(s) sem frete para o CEP")
    return ofertas
