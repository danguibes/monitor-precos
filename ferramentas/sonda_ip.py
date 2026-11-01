"""Sonda de bloqueio por IP: as mesmas requisições, daqui e de uma máquina de nuvem.

Rodar nos dois lugares e comparar: o que muda entre eles é efeito do IP. Só
biblioteca padrão, para rodar igual no GitHub Actions. Usa um CEP genérico
(Av. Paulista), nunca o de local.toml: o log do Actions é público.

As lojas que o monitor consulta pelo navegador entram aqui como uma requisição
simples, sem navegador: o número absoluto não é o do monitor, mas a COMPARAÇÃO
entre os dois IPs é justa, porque a requisição é idêntica.

    py ferramentas/sonda_ip.py
"""
import json
import re
import time
import urllib.error
import urllib.request

CEP_GENERICO = "01310100"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/130.0 Safari/537.36")
SINAIS = re.compile(r"captcha|are you a robot|não sou um robô|robot check|access denied|acesso negado|"
                    r"px-captcha|perimeterx|cf-chl|challenge-platform|akamai|unusual traffic|"
                    r"tráfego incomum|account-verification", re.I)

SONDAS = [
    # (loja, como o monitor consulta, url, corpo POST ou None)
    ("Mambo (VTEX)", "API", "https://www.mambo.com.br/api/catalog_system/pub/products/search?ft=agua%20com%20gas", None),
    ("Atacadão (VTEX)", "API", "https://www.atacadao.com.br/api/catalog_system/pub/products/search?ft=agua%20com%20gas", None),
    ("Oba (VTEX)", "API", "https://www.obahortifruti.com.br/api/catalog_system/pub/products/search?ft=agua%20com%20gas", None),
    ("Fast Shop (VTEX)", "API", "https://site.fastshop.com.br/api/catalog_system/pub/products/search?ft=freezer", None),
    ("Mambo frete (VTEX)", "API", f"https://www.mambo.com.br/api/checkout/pub/regions?country=BRA&postalCode={CEP_GENERICO}", None),
    ("Pão de Açúcar entrega", "API", f"https://api.vendas.gpa.digital/pa/delivery-v2/ecom/deliveryOptions?zipCode={CEP_GENERICO}", None),
    ("Mercado Livre API", "API oficial", "https://api.mercadolibre.com/sites/MLB/search?q=agua%20com%20gas", None),
    ("Mercado Livre busca", "navegador", "https://lista.mercadolivre.com.br/agua-com-gas", None),
    ("Amazon busca", "navegador", "https://www.amazon.com.br/s?k=agua+com+gas", None),
    ("Magalu busca", "navegador", "https://www.magazineluiza.com.br/busca/agua+com+gas/", None),
    ("Casas Bahia busca", "navegador", "https://www.casasbahia.com.br/agua-com-gas/b", None),
    ("Carrefour", "navegador", "https://www.carrefour.com.br/", None),
    ("Vila das Frutas", "navegador", "https://www.viladasfrutas.com.br/", None),
]


def pedir(url, corpo=None):
    req = urllib.request.Request(url, data=json.dumps(corpo).encode() if corpo else None,
                                 headers={"User-Agent": UA, "Accept-Language": "pt-BR,pt;q=0.9",
                                          "Accept": "text/html,application/json;q=0.9,*/*;q=0.8"})
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=25) as r:
            corpo_r = r.read(400_000).decode("utf-8", "ignore")
            return r.status, r.geturl(), corpo_r, time.time() - t0
    except urllib.error.HTTPError as e:
        return e.code, url, e.read(50_000).decode("utf-8", "ignore"), time.time() - t0
    except Exception as e:  # rede, TLS, tempo
        return 0, url, f"{e.__class__.__name__}: {e}", time.time() - t0


def veredito(status, url_pedida, url_final, corpo):
    if status == 0:
        return "FALHA DE REDE"
    if status in (403, 429, 503) or (status >= 400 and SINAIS.search(corpo)):
        return f"BLOQUEADO ({status})"
    if re.search(r"captcha|login|account-verification|validatecaptcha", url_final, re.I) and url_final != url_pedida:
        return "DESVIADO p/ captcha/login"
    if SINAIS.search(corpo[:60_000]) and len(corpo) < 60_000:
        return "DESAFIO na página"
    return f"ok ({status})"


def main():
    s, _, corpo, _ = pedir("https://ipinfo.io/json")
    try:
        info = json.loads(corpo)
        print(f"Rede de saída: {info.get('org', '?')} · {info.get('country', '?')}")  # sem o IP em si
    except ValueError:
        print("Rede de saída: ?")
    print(f"{'loja':24s} {'como':12s} {'resultado':26s} {'KB':>6s} {'s':>5s}")
    for loja, como, url, corpo_req in SONDAS:
        status, final, corpo, dt = pedir(url, corpo_req)
        print(f"{loja:24s} {como:12s} {veredito(status, url, final, corpo):26s} {len(corpo)/1024:6.0f} {dt:5.1f}")
        time.sleep(2)  # a sonda também não martela ninguém


if __name__ == "__main__":
    main()
