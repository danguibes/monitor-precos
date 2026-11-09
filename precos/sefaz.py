"""As NFC-e que o Augustinus não consegue ler, abertas pelo navegador desta máquina.

Desde 08/11/2026 a SEFAZ-SP recusa o servidor do Augustinus. Medido em 09/11: daqui de casa
um script também é recusado (conexão negada, reset), e o Chrome do monitor abre o link do QR
em 4,5 s, sem captcha, com a nota inteira. O que passa é o navegador, não o endereço.

O monitor só busca e entrega: lê as chaves em monitor.chaves_pendentes (papel monitor_precos)
e grava a página como veio em recebido.paginas_sefaz (papel monitor_pedidos, só INSERT); quem
lê a nota é o Augustinus. A consulta por formulário tem captcha e fica fora: só o link do QR,
e página com captcha ou rejeição não é gravada nem contornada.
"""
from __future__ import annotations

import re
import time

from .augustinus import conectar
from .base import RAIZ, carregar_json, log, salvar_json

ESTADO = RAIZ / "dados" / "sefaz.json"
MAX_POR_RODADA = 5
PAUSA = 8.0
_SO_SEFAZ = re.compile(r"^https://(www\.)?nfce\.fazenda\.sp\.gov\.br/", re.I)


def problema_da_pagina(status: int | None, html: str, texto: str, chave: str) -> str | None:
    """None se a página é a nota pedida; senão, o motivo de não gravar."""
    if status != 200:
        return f"status {status}"
    if re.search(r"captcha", html, re.I):
        return "captcha"
    if "Request Rejected" in html:
        return "rejeitada pela SEFAZ"
    if not re.search(r"Valor a pagar", texto, re.I):
        return "sem o valor da nota"
    if chave not in re.sub(r"\D", "", texto):
        return "a chave não está na página"
    return None


def ler_pendentes(leitura: dict) -> list[tuple[str, str]]:
    con = conectar(leitura)
    try:
        linhas = con.run("select chave, url from monitor.chaves_pendentes")
    finally:
        con.close()
    return [(str(c), str(u)) for c, u in linhas if c and u and _SO_SEFAZ.match(str(u))]


def gravar(paginas: list[dict], escrita: dict) -> None:
    con = conectar(escrita)
    try:
        for p in paginas:
            con.run("insert into recebido.paginas_sefaz (chave, url, url_final, html) "
                    "values (:chave, :url, :url_final, :html) on conflict do nothing", **p)
    finally:
        con.close()


def visitar(page, pendentes: list[tuple[str, str]]) -> tuple[list[dict], list[str]]:
    from .navegador import texto
    paginas, avisos = [], []
    for n, (chave, url) in enumerate(pendentes[:MAX_POR_RODADA]):
        if n:
            time.sleep(PAUSA)
        try:
            r = page.goto(url, wait_until="domcontentloaded", timeout=45000)
            time.sleep(4)
            html = page.content()
            motivo = problema_da_pagina(r.status if r else None, html, texto(page), chave)
        except Exception as exc:
            motivo, html = type(exc).__name__, ""
        fim = chave[-6:]
        if motivo:
            avisos.append(f"nota …{fim}: {motivo}; nada gravado")
            if motivo in ("captcha", "rejeitada pela SEFAZ"):
                avisos.append("parei as notas desta rodada")
                break
            continue
        paginas.append({"chave": chave, "url": url, "url_final": page.url, "html": html})
    return paginas, avisos


def rodar(cfg: dict, leitura: dict, escrita: dict | None, ensaio: bool) -> int:
    from datetime import date
    from .navegador import abrir_navegador

    pendentes = ler_pendentes(leitura)
    if not pendentes:
        log("Notas da SEFAZ: nenhuma pendente.")
        if not ensaio:
            salvar_json(ESTADO, {"ultima": date.today().isoformat()})
        return 0
    pw, ctx = abrir_navegador(cfg, visivel=False)
    try:
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        paginas, avisos = visitar(page, pendentes)
    finally:
        ctx.close()
        pw.stop()
    for a in avisos:
        log("Notas da SEFAZ: " + a)
    if ensaio:
        log(f"Notas da SEFAZ (ensaio, nada gravado): {len(paginas)} de {len(pendentes)} pendentes abririam.")
        return len(paginas)
    if not escrita:
        log("Notas da SEFAZ: falta a seção [augustinus_pedidos] no local.toml; nada gravado.")
        return 0
    if paginas:
        gravar(paginas, escrita)
    log(f"Notas da SEFAZ: {len(paginas)} página(s) entregue(s) ao Augustinus, de {len(pendentes)} pendente(s).")
    salvar_json(ESTADO, {"ultima": date.today().isoformat()})
    return len(paginas)


def feito_hoje() -> bool:
    from datetime import date
    return carregar_json(ESTADO, {}).get("ultima") == date.today().isoformat()
