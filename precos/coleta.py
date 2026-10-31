"""Orquestra a coleta: lojas VTEX por API, lojas com API própria e lojas do navegador."""
from __future__ import annotations

from datetime import datetime

from .filtros import criar_filtro
from .lojas import (amazon, carrefour, casas_bahia, magalu, mercado_livre, pao_de_acucar, shopee,
                    vila_das_frutas, vtex)
from .navegador import abrir_navegador
from .unidades import montar_pack

COLETORES = {
    "Carrefour": carrefour.coletar,
    "Magalu": magalu.coletar,
    "Casas Bahia": casas_bahia.coletar,
    "Mercado Livre": mercado_livre.coletar,
    "Shopee": shopee.coletar,
    "Vila das Frutas": vila_das_frutas.coletar,
    "Amazon": amazon.coletar,
}
# lojas com API própria (sem navegador e fora da VTEX)
COLETORES_API = {
    "Pão de Açúcar": pao_de_acucar.coletar,
}

coletar_api = vtex.coletar


def buscas(cfg: dict) -> list[dict]:
    """O que se procura em cada loja. No modo descoberta, um item por termo de busca."""
    if cfg.get("modo") == "descoberta":
        return [{"modelo": cfg["titulo"], "busca": t} for t in cfg["termos"]]
    return cfg["produtos"]


def deduplicar(ofertas):
    """Mesma loja, mesmo anúncio e mesmo vendedor: fica a mais barata.

    Acontece quando dois termos de busca acham o mesmo anúncio, e no Magalu,
    que repetia o anúncio dentro da mesma busca.
    """
    unicos = {}
    for o in ofertas:
        chave = (o["loja"], o["sku"] or o["link"], o["vendedor"])
        if chave not in unicos or (o["total_pix"] or 0) < (unicos[chave]["total_pix"] or 0):
            unicos[chave] = o
    return list(unicos.values())


def coletar_tudo(cfg: dict, estado: dict, log, com_navegador: bool = True):
    produtos = buscas(cfg)
    filtro = criar_filtro(cfg)
    descoberta = cfg.get("modo") == "descoberta"
    data = datetime.now().strftime("%Y-%m-%d %H:%M")

    ofertas, erros = [], []
    if cfg.get("lojas"):
        log("Consultando lojas (API)...")
        ofertas, erros = coletar_api(cfg, estado, produtos, filtro if descoberta else None)
        data = ofertas[0]["data"] if ofertas else data
    for loja in cfg.get("lojas_api", []):
        if loja in COLETORES_API:
            log(f"  {loja}...")
            r = COLETORES_API[loja](cfg, produtos, data, filtro, erros)
            log(f"    {len(r)} ofertas")
            ofertas += r
    if com_navegador and cfg.get("lojas_navegador"):
        log("Consultando lojas pelo navegador...")
        try:
            nav, erros_nav = coletar_navegador(cfg, produtos, data, filtro, log)
            ofertas += nav
            erros += erros_nav
        except ImportError:
            erros.append("Playwright não instalado: rode 'py instalar.py' de novo.")
    for o in ofertas:
        o["data"] = data  # uma rodada, uma data, mesmo que leve minutos
        if descoberta:
            o["modelo"] = o["loja"]  # no modo descoberta, um card por loja
    pack = (cfg.get("regras") or {}).get("montar_pack")
    if pack:
        ofertas = [x for x in (montar_pack(o, pack) for o in ofertas) if x]
    return deduplicar(ofertas), erros


def coletar_navegador(cfg, produtos, data, filtros, log):
    lojas = [l for l in cfg.get("lojas_navegador", list(COLETORES)) if l in COLETORES]
    if not lojas:
        return [], []
    try:
        pw, ctx = abrir_navegador(cfg)
    except Exception as e:
        return [], [f"Navegador não abriu ({e}). Rode 'py instalar.py' de novo."]
    ofertas, erros = [], []
    try:
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        for loja in lojas:
            log(f"  {loja}...")
            try:
                r = COLETORES[loja](page, cfg, produtos, data, filtros, erros)
                ofertas += r
                log(f"    {len(r)} ofertas")
            except Exception as e:
                erros.append(f"{loja}: erro inesperado ({e.__class__.__name__}: {e})")
    finally:
        try:
            ctx.close()
            pw.stop()
        except Exception:
            pass
    return ofertas, erros
