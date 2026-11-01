"""Segunda sonda de IP: as lojas que o monitor consulta pelo NAVEGADOR, com navegador.

A sonda_ip.py usa requisição simples, e Mercado Livre, Amazon, Magalu e Casas Bahia
já a recusam de casa — então ela não diz se o navegador seria barrado na nuvem.
Esta abre as mesmas páginas no Google Chrome, com perfil NOVO e sem login (o
mesmo nos dois lugares: o que muda é só o IP), e diz se veio página de produtos
(conta preços "R$") ou desafio/captcha. Janela real, não headless: no Actions
roda sob xvfb.

    py ferramentas/sonda_navegador.py
"""
import re
import tempfile
import time

PAGINAS = [
    ("Mercado Livre", "https://lista.mercadolivre.com.br/agua-com-gas"),
    ("Amazon", "https://www.amazon.com.br/s?k=agua+com+gas"),
    ("Magalu", "https://www.magazineluiza.com.br/busca/agua+com+gas/"),
    ("Casas Bahia", "https://www.casasbahia.com.br/agua-com-gas/b"),
    ("Carrefour", "https://www.carrefour.com.br/busca/agua%20com%20gas"),
    ("Vila das Frutas", "https://www.viladasfrutas.com.br/busca/agua%20com%20gas"),
]
DESAFIO = re.compile(r"captcha|não sou um robô|are you a robot|robot check|acesso negado|access denied|"
                     r"tráfego incomum|unusual traffic|verifique que você|confirme que você|"
                     r"press & hold|pressione e segure|account-verification", re.I)


def main(rodadas=2):
    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw, tempfile.TemporaryDirectory() as perfil:
        # o Chrome aberto como o monitor abre (precos/navegador.py), só que sem login:
        # sem estas duas opções o Magalu responde "Não é possível acessar a página"
        ctx = pw.chromium.launch_persistent_context(perfil, channel="chrome", headless=False, locale="pt-BR",
                                                    viewport={"width": 1280, "height": 900},
                                                    args=["--lang=pt-BR", "--disable-blink-features=AutomationControlled"],
                                                    ignore_default_args=["--enable-automation"])
        page = ctx.new_page()
        print(f"{'loja':16s} {'resultado':34s} {'preços':>6s}  título")
        for loja, url in PAGINAS * rodadas:  # duas passadas: uma só já se mostrou instável (Amazon)
            try:
                resp = page.goto(url, wait_until="domcontentloaded", timeout=45000)
                time.sleep(6)
                page.mouse.wheel(0, 1500)  # Magalu e Casas Bahia carregam a lista ao rolar
                time.sleep(4)
                texto = page.inner_text("body")[:200_000]
                status = resp.status if resp else 0
            except Exception as e:
                print(f"{loja:16s} {'FALHA: ' + e.__class__.__name__:34s}")
                continue
            precos = len(re.findall(r"R\$\s*\d", texto))
            if DESAFIO.search(page.url) or (DESAFIO.search(texto) and precos < 3):
                res = f"DESAFIO/captcha ({status})"
            elif status >= 400 and precos < 3:
                res = f"BLOQUEADO ({status})"
            elif precos >= 3:
                res = f"ok, produtos ({status})"
            else:
                res = f"página sem preços ({status})"
            print(f"{loja:16s} {res:34s} {precos:6d}  {page.title()[:45]}")
            time.sleep(4)
        ctx.close()


if __name__ == "__main__":
    main()
