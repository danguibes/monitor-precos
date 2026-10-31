"""
Salva respostas reais das lojas em tests/fixtures/<loja>/, para os testes dos leitores.

  py ferramentas/salvar_fixture.py vtex <host> <sku> <vendedor> <nome>
      grava a simulação de frete (JSON)

  py ferramentas/salvar_fixture.py pagina <loja> <url> <nome> [--cep]
      abre a página no navegador do monitor e grava o texto visível (.txt) e o
      HTML (.html); com --cep, preenche o CEP antes (Casas Bahia)

Os sites mudam de layout: quando um teste quebrar, capture de novo a página,
compare com a fixture antiga e só então ajuste o leitor.

O repositório é público: por padrão as fixtures usam um CEP neutro (Av.
Paulista), não o de local.toml. --cep-de-casa usa o de casa, e aí a fixture
precisa ser limpa antes de ir para o git.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))


FIXTURES = RAIZ / "tests" / "fixtures"
CEP_NEUTRO = "01310-100"  # Av. Paulista: fixture que vai para o repositório público não leva o CEP de casa


def config_com_cep():
    """O cfg do primeiro monitor, com o CEP neutro — a não ser que se peça --cep-de-casa."""
    from precos.monitores import carregar
    cfg = dict(carregar()[0]["cfg"])
    if "--cep-de-casa" not in sys.argv:
        cfg["cep"] = CEP_NEUTRO
    return cfg


def vtex(host, sku, vendedor, nome):
    from precos.lojas.vtex import simular_com_canal
    cfg = config_com_cep()
    sim = simular_com_canal(host, sku, vendedor, re.sub(r"\D", "", cfg["cep"]), {})
    if not sim:
        sys.exit("A simulação não respondeu.")
    destino = FIXTURES / "vtex" / f"{nome}.json"
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(json.dumps(sim, ensure_ascii=False, indent=1), encoding="utf-8")
    print("Gravado:", destino)


def pagina(loja, url, nome, com_cep):
    from precos.navegador import abrir_navegador, ir, texto
    cfg = config_com_cep()
    pw, ctx = abrir_navegador(cfg)
    try:
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        if not ir(page, url, espera=4):
            sys.exit("A página não abriu.")
        if com_cep:
            campo = page.locator("input[placeholder='_____-___']").first
            campo.fill(re.sub(r"\D", "", cfg["cep"]))
            campo.press("Enter")
            page.wait_for_timeout(5000)
        pasta = FIXTURES / loja
        pasta.mkdir(parents=True, exist_ok=True)
        (pasta / f"{nome}.txt").write_text(texto(page), encoding="utf-8")
        (pasta / f"{nome}.html").write_text(page.content(), encoding="utf-8")
        print("Gravado:", pasta / f"{nome}.txt", "e .html")
    finally:
        ctx.close()
        pw.stop()


if __name__ == "__main__":
    a = [x for x in sys.argv[1:] if x != "--cep-de-casa"]
    if len(a) == 5 and a[0] == "vtex":
        vtex(*a[1:])
    elif len(a) >= 4 and a[0] == "pagina":
        pagina(a[1], a[2], a[3], "--cep" in a)
    else:
        sys.exit(__doc__)
