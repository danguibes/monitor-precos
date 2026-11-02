"""Orquestra a coleta: lojas VTEX por API, lojas com API própria e lojas do navegador."""
from __future__ import annotations

from datetime import datetime

from .filtros import criar_filtro
from .lojas import (amazon, carrefour, casas_bahia, madeiramadeira, magalu, mercado_livre, mercado_livre_api, pao_de_acucar,
                    rappi, shopee, vila_das_frutas, vtex)
from .navegador import abrir_navegador
from .unidades import montar_pack

COLETORES = {
    "Carrefour": carrefour.coletar,
    "Magalu": magalu.coletar,
    "Casas Bahia": casas_bahia.coletar,
    "MadeiraMadeira": madeiramadeira.coletar,
    "Mercado Livre": mercado_livre.coletar,
    "Shopee": shopee.coletar,
    "Vila das Frutas": vila_das_frutas.coletar,
    "Amazon": amazon.coletar,
    "Assaí": rappi.coletar,  # pelo Rappi: o Assaí não entrega por conta própria
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
    # Monitor de marca: o catálogo do Mercado Livre pela API oficial, sem login nem captcha.
    #   mercado_livre = "ambos": API e navegador (o catálogo não tem tudo: em 01/11 o
    #                            colchão Emma avulso só estava fora dele);
    #   mercado_livre = "api":   só a API — o Mercado Livre sai do navegador.
    # Sem acesso à API, o navegador segue nesta rodada e a página avisa.
    nav_lojas = list(cfg.get("lojas_navegador", []))
    if cfg.get("mercado_livre") in ("api", "ambos") and "Mercado Livre" in nav_lojas:
        log("  Mercado Livre (API)...")
        try:
            r = mercado_livre_api.coletar(cfg, produtos, data, filtro, erros)
            log(f"    {len(r)} ofertas")
            ofertas += r
            if cfg["mercado_livre"] == "api":
                nav_lojas.remove("Mercado Livre")
        except mercado_livre_api.SemAcesso as e:
            erros.append(f"Mercado Livre: API indisponível ({e}); consultado pelo navegador")
    if com_navegador and nav_lojas:
        log("Consultando lojas pelo navegador...")
        try:
            nav, erros_nav = coletar_navegador(dict(cfg, lojas_navegador=nav_lojas), produtos, data, filtro, log)
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
    # depois do pack: a taxa é sobre o subtotal, e o subtotal de 6 garrafas é 6 vezes o de uma
    ofertas = [somar_taxa_servico(o, taxas_de_servico(cfg)) for o in ofertas]
    return deduplicar(ofertas), erros


def taxas_de_servico(cfg: dict) -> dict[str, float]:
    """{loja: fração} das lojas com `taxa_servico` em lojas.toml (Atacadão: 0.06), mais a do Rappi,
    que é da plataforma e não da loja: vale para o Assaí e para qualquer loja que vier por ele."""
    taxas = {l["nome"]: float(l["taxa_servico"]) for l in cfg.get("lojas", []) if l.get("taxa_servico")}
    return taxas | {rappi.LOJA: rappi.TAXA_SERVICO}


def somar_taxa_servico(o: dict, taxas: dict) -> dict:
    """A taxa de serviço da loja entra no frete: "frete" passa a ser o que se paga além dos itens."""
    t = taxas.get(o["loja"])
    if not t or o.get("preco_pix") is None or o.get("frete") is None:
        return o  # entrega desconhecida (Rappi sem login): taxa sem frete daria um total que parece certo
    o = dict(o)
    taxa = round(o["preco_pix"] * t + 1e-9, 0 if o["loja"] == rappi.LOJA else 2)
    o["frete"] = round((o["frete"] or 0) + taxa, 2)
    o["total_pix"] = round(o["preco_pix"] + o["frete"], 2)
    o["total_cartao"] = round((o["preco"] or o["preco_pix"]) + o["frete"], 2)
    o["prazo"] = f'{o["prazo"]} · frete inclui taxa de serviço de {t:.0%}'.lstrip(" ·")
    return o


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
