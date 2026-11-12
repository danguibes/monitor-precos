"""Sonda da Oxylabs contra o gabarito do monitor: as mesmas páginas, já lidas aqui.

Escolhe páginas de produto da última rodada de cada monitor nas lojas que bloqueiam a
nuvem (medido em 31/10: Mercado Livre com captcha, Magalu e Carrefour 403, Casas Bahia
vazia) e na Amazon, pede cada uma ao Web API da Oxylabs (o produto do painel novo, de
10/2026: /v1/scrape com navegador e saída pelo Brasil) e confere se o preço que o monitor leu está na página que voltou.

Responde a "a Oxylabs entrega a página certa do Brasil?" e não a "ela lê o frete do meu
CEP": sem sessão com CEP, a página traz o preço de prateleira. O frete é a pergunta para
a reunião, não para esta sonda.

Custo: ~US$ 1,50 por mil páginas com navegador; 20 páginas são ~US$ 0,03 do crédito.
A chave do Web API (painel: criar a instância do Web API e gerar a chave nela; o Web API
recusa usuário e senha) fica em local.toml, nunca no código:

    [oxylabs]
    chave = "..."

    py ferramentas/sonda_oxylabs.py --listar   -> só mostra o que seria pedido, sem gastar
    py ferramentas/sonda_oxylabs.py            -> pede as páginas e compara
"""
import json
import re
import sys
import time
import tomllib
import urllib.error
import urllib.request
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
sys.stdout.reconfigure(encoding="utf-8")

from precos import monitores as mon  # noqa: E402
from precos.historico import ler_historico  # noqa: E402

ENDPOINT = "https://webapi.oxylabs.io/v1/scrape"
LOJAS = {"Mercado Livre": 5, "Magalu": 4, "Casas Bahia": 4, "Carrefour": 4, "Amazon": 3}
BLOQUEIO = re.compile(r"captcha|are you a robot|não sou um robô|robot check|access denied|acesso negado|"
                      r"px-captcha|perimeterx|unusual traffic|tráfego incomum|account-verification", re.I)


def escolher() -> list[dict]:
    """Da última rodada de cada monitor, até N páginas por loja, uma por monitor e loja."""
    por_loja: dict[str, list] = {l: [] for l in LOJAS}
    for m in mon.carregar(precisa_cep=False):
        linhas = [l for l in ler_historico(m["historico"]) if l.get("link", "").startswith("http")]
        if not linhas:
            continue
        ultima = max(l["data"] for l in linhas)[:13]
        vistos = set()
        for l in sorted(linhas, key=lambda l: l["data"], reverse=True):
            if l["data"][:13] != ultima or l["loja"] not in LOJAS or l["loja"] in vistos or not l.get("preco"):
                continue
            if re.match(r"^\d+\s*×", l["produto"]):  # pacote montado pelo monitor: a página traz o preço de UMA
                continue
            vistos.add(l["loja"])
            por_loja[l["loja"]].append({"monitor": m["id"], "loja": l["loja"], "produto": l["produto"],
                                        "preco": l["preco"], "preco_pix": l.get("preco_pix"), "link": l["link"]})
    return [p for loja, n in LOJAS.items() for p in por_loja[loja][:n]]


def formas(valor: float | None) -> set[str]:
    """Como o preço pode estar escrito na página: 1.234,56 · 1234,56 · 1234.56 (JSON-LD)."""
    if not valor:
        return set()
    br = f"{valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return {br, br.replace(".", ""), f"{valor:.2f}", br.removesuffix(",00")}


def pedir(url: str, chave: str) -> tuple[int | None, str, float, str]:
    corpo = json.dumps({"url": url, "output": ["html"], "run_js": True, "location": "BR"}).encode()
    req = urllib.request.Request(ENDPOINT, data=corpo, method="POST",
                                 headers={"Content-Type": "application/json", "Authorization": f"Bearer {chave}"})
    t = time.time()
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            dados = json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, "", time.time() - t, e.read().decode("utf-8", "replace")[:200]
    except Exception as e:
        return None, "", time.time() - t, f"{type(e).__name__}: {e}"[:200]
    res = (dados.get("results") or [{}])[0]
    # "status" é documentado como 200 em sucesso; se é o da loja ou só o do pedido, a doc não diz
    return dados.get("status"), res.get("html") or "", time.time() - t, ""


def main(argv: list[str]) -> int:
    paginas = escolher()
    print(f"{len(paginas)} página(s):", ", ".join(f"{l} {sum(p['loja'] == l for p in paginas)}" for l in LOJAS))
    if "--listar" in argv:
        for p in paginas:
            print(f"  {p['loja']:<13} | {p['monitor']:<26} | R$ {p['preco']:>9.2f} | {p['produto'][:55]}")
        return 0
    cred = tomllib.loads((RAIZ / "local.toml").read_text(encoding="utf-8")).get("oxylabs") or {}
    if not cred.get("chave"):
        print("Falta a seção [oxylabs] com a chave do Web API no local.toml.")
        return 1
    achou = 0
    for n, p in enumerate(paginas, 1):
        status, html, seg, erro = pedir(p["link"], cred["chave"])
        if status in (401, 403) and not html:
            print(f"Credencial recusada ({status}): {erro}. Parei para não insistir.")
            return 1
        bate = bool(html) and any(f in html for f in formas(p["preco"]) | formas(p["preco_pix"]))
        bloqueio = bool(BLOQUEIO.search(html[:20000])) if html else False
        achou += bate
        print(f"{n:>2} {p['loja']:<13} | {p['monitor']:<26} | status {status} | {seg:5.1f} s | "
              f"{len(html) // 1024:>4} KB | preço {'ACHOU' if bate else 'não achou'}"
              f"{' | BLOQUEIO' if bloqueio else ''}{' | ' + erro if erro else ''}")
    print(f"\nPreço do monitor encontrado em {achou} de {len(paginas)} página(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
