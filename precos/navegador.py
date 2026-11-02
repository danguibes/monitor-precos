"""O navegador do monitor, para as lojas que só respondem a um navegador de verdade.

Usa o Playwright pilotando o Google Chrome instalado, com um perfil próprio
guardado em dados/perfil-navegador (separado do seu Chrome do dia a dia).
Mercado Livre e Shopee exigem login: faça uma vez com
    py monitor.py --configurar
"""
from __future__ import annotations

import time

from .base import PERFIL


# Sites em que o perfil do monitor entra com a SUA conta: um bloqueio ali não fica
# na loja, chega à conta. Cada página deles espera `pausa_lojas_com_login` segundos
# a mais (config.toml). O Mercado Livre já pediu captcha com quatro monitores.
COM_LOGIN = ("mercadolivre.com.br", "viladasfrutas.com.br", "rappi.com.br")
_pausa_com_login = 6.0


def abrir_navegador(cfg: dict, visivel: bool | None = None):
    """Retorna (playwright, contexto). O chamador fecha os dois."""
    from playwright.sync_api import sync_playwright  # import tardio: só se usar

    global _pausa_com_login
    _pausa_com_login = float(cfg.get("pausa_lojas_com_login", _pausa_com_login))

    if visivel is None:
        visivel = bool(cfg.get("navegador_visivel", False))
    pw = sync_playwright().start()
    args = ["--disable-blink-features=AutomationControlled", "--lang=pt-BR"]
    if not visivel:
        # janela real (não headless, que os sites bloqueiam), só que fora da tela
        args += ["--window-position=-32000,-32000", "--window-size=1280,900"]
    opcoes = dict(user_data_dir=str(PERFIL), headless=False, args=args,
                  locale="pt-BR", viewport={"width": 1280, "height": 900},
                  ignore_default_args=["--enable-automation"])
    try:
        ctx = pw.chromium.launch_persistent_context(channel="chrome", **opcoes)
    except Exception as chrome:
        try:
            ctx = pw.chromium.launch_persistent_context(**opcoes)  # Chromium do Playwright
        except Exception as e:
            # sem o stop, o Playwright fica preso ao processo e todo monitor seguinte da
            # rodada cai em "Sync API inside the asyncio loop" (01/11/2026, perfil em uso)
            pw.stop()
            raise RuntimeError(f"Chrome: {chrome}".split("\n")[0] + f" | Chromium: {e}".split("\n")[0]) from e
    ctx.set_default_timeout(25000)
    return pw, ctx


def ir(page, url: str, espera: float = 2.5) -> bool:
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=45000)
    except Exception:
        return False
    time.sleep(espera + (_pausa_com_login if any(h in url for h in COM_LOGIN) else 0))
    return True


def texto(page) -> str:
    try:
        return page.inner_text("body", timeout=10000)
    except Exception:
        return ""


PAGINAS_CONFIGURAR = ["https://www.mercadolivre.com.br/", "https://shopee.com.br/buyer/login",
                      "https://www.magazineluiza.com.br/", "https://www.casasbahia.com.br/",
                      "https://www.carrefour.com.br/", "https://www.viladasfrutas.com.br/",
                      "https://www.amazon.com.br/", "https://www.rappi.com.br/lojas/tipo/supermercados"]


def configurar(cfg, filtro: str = ""):
    """Abre o navegador do monitor, visível, para login e CEP. Espera você fechar.

    Com `filtro` (ex.: "viladasfrutas"), abre só as páginas cujo endereço o contém.
    """
    pw, ctx = abrir_navegador(cfg, visivel=True)
    paginas = [u for u in PAGINAS_CONFIGURAR if filtro in u] or PAGINAS_CONFIGURAR
    p0 = ctx.pages[0] if ctx.pages else ctx.new_page()
    p0.goto(paginas[0])
    for u in paginas[1:]:
        ctx.new_page().goto(u, wait_until="domcontentloaded")
    print("\nNo navegador que abriu:\n"
          "  1. Mercado Livre, Shopee, Vila das Frutas e Rappi: entre na sua conta (o ML usa o endereço\n"
          "     padrão da conta para o frete; na Vila das Frutas, escolha Entrega e o endereço de casa;\n"
          "     no Rappi, o endereço de casa — é ele que escolhe a loja Assaí e a taxa).\n"
          f"  2. Magalu, Casas Bahia e Carrefour: informe o CEP {cfg['cep']} se pedirem.\n"
          "  3. Feche a janela do navegador quando terminar.\n")
    try:
        ctx.wait_for_event("close", timeout=0)
    except Exception:
        pass
    try:
        pw.stop()
    except Exception:
        pass
