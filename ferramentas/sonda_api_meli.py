"""O que a API oficial do Mercado Livre responde para o monitor, com o token do app.

Credenciais em local.toml (fora do git):
    [mercadolivre]
    client_id = "..."
    client_secret = "..."

O token (client_credentials) é pedido na hora e nunca impresso; o CEP do
local.toml é usado no frete e também não aparece na saída.

    py ferramentas/sonda_api_meli.py
"""
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from precos import monitores as mon  # noqa: E402

API = "https://api.mercadolibre.com"


def pedir(caminho, token=None, dados=None):
    req = urllib.request.Request(API + caminho, data=dados,
                                 headers={"Accept": "application/json",
                                          **({"Authorization": f"Bearer {token}"} if token else {}),
                                          **({"Content-Type": "application/x-www-form-urlencoded"} if dados else {})})
    try:
        with urllib.request.urlopen(req, timeout=25) as r:
            return r.status, json.loads(r.read().decode("utf-8") or "null")
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode("utf-8") or "null")
        except ValueError:
            return e.code, None
    finally:
        time.sleep(0.5)


def resumo(status, corpo):
    if status != 200:
        msg = (corpo or {}).get("message") or (corpo or {}).get("code") or (corpo or {}).get("error") if isinstance(corpo, dict) else ""
        return f"{status} {msg}"[:70]
    return f"{status} ok"


def main():
    local = mon.ler_toml(mon.LOCAL, obrigatorio=False)
    ml = local.get("mercadolivre") or {}
    if not ml.get("client_id") or not ml.get("client_secret"):
        sys.exit("Falta [mercadolivre] client_id e client_secret no local.toml.")
    cep = re.sub(r"\D", "", local.get("cep", ""))

    st, tok = pedir("/oauth/token", dados=urllib.parse.urlencode({
        "grant_type": "client_credentials", "client_id": ml["client_id"], "client_secret": ml["client_secret"]}).encode())
    if st != 200 or not isinstance(tok, dict) or not tok.get("access_token"):
        sys.exit(f"Token do app recusado: {resumo(st, tok)}")
    token = tok["access_token"]
    print(f"Token do app: ok (escopo '{tok.get('scope', '?')}', vale {tok.get('expires_in', '?')} s)")

    linhas = []

    def medir(nome, caminho, com_token=True):
        st, corpo = pedir(caminho, token if com_token else None)
        linhas.append((nome, "com token" if com_token else "sem token", resumo(st, corpo)))
        return st, corpo

    medir("busca aberta /sites/MLB/search", "/sites/MLB/search?q=colchao%20emma%20casal&limit=5")
    st, cat = medir("catálogo /products/search", "/products/search?status=active&site_id=MLB&q=colchao%20emma%20casal")
    produtos = cat.get("results", []) if st == 200 and isinstance(cat, dict) else []
    if produtos:
        print(f"  catálogo: {cat.get('paging', {}).get('total', '?')} produtos; primeiros: "
              + " | ".join(p.get("name", "")[:40] for p in produtos[:5]))
    item, sem_anuncio = None, 0
    for produto in produtos[:10]:  # o 1º pode não ter anúncio vendendo ("No winners found")
        st, itens = pedir(f"/products/{produto['id']}/items", token)
        if st == 200 and isinstance(itens, dict) and itens.get("results"):
            linhas.append(("anúncios do produto /products/{id}/items", "com token",
                           f"200 ok (após {sem_anuncio} sem anúncio)"))
            r0 = itens["results"][0]
            item = r0.get("item_id")
            print(f"  anúncios de '{produto.get('name', '')[:50]}': {len(itens['results'])}; 1º: R$ {r0.get('price')} · "
                  f"frete grátis {((r0.get('shipping') or {}).get('free_shipping'))} · "
                  f"condição {r0.get('condition')}")
            break
        sem_anuncio += 1
    else:
        linhas.append(("anúncios do produto /products/{id}/items", "com token", f"nenhum dos {sem_anuncio} tem anúncio"))
    if item:
        medir("ficha do anúncio /items/{id}", f"/items/{item}")
        medir("frete p/ o CEP /items/{id}/shipping_options", f"/items/{item}/shipping_options?zip_code={cep}")
        st, fr = pedir(f"/items/{item}/shipping_options?zip_code={cep}", token)
        if st == 200 and isinstance(fr, dict):
            opcoes = [(o.get("name"), o.get("cost"), (o.get("estimated_delivery_time") or {}).get("date"))
                      for o in fr.get("options") or []]
            print(f"  frete para o CEP de local.toml: {opcoes[:3]}")
        medir("frete sem token", f"/items/{item}/shipping_options?zip_code={cep}", com_token=False)

    print(f"\n{'caminho':44s} {'como':10s} resultado")
    for nome, como, res in linhas:
        print(f"{nome:44s} {como:10s} {res}")


if __name__ == "__main__":
    main()
