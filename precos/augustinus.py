"""O que a casa paga no supermercado, pelo Augustinus, para destacar oferta muito boa.

Lê monitor.compras_da_casa no banco do Augustinus com o papel monitor_precos,
que só enxerga essa view (migrations 0082 e 0083 de lá). Credenciais em
local.toml, seção [augustinus], fora do git; o certificado da CA do Supabase
fica em certificados/, e a conexão verifica cadeia e nome.

A conta é sempre na unidade do monitor, e é aqui que se erra calado:

  * monitor por LITRO (tem volume_ml nas regras): o volume vem do CATÁLOGO do
    Augustinus (quantidade_base, já multiplicado pela embalagem). Nunca do texto
    do cupom: "AGUA MINMINALBA 15L" é 1,5 L cortado, e lido como 15 L daria um
    preço por litro absurdo. Catálogo sem medida → a compra fica fora.
  * monitor por UNIDADE (rolos, latas): a contagem vem do TEXTO do cupom ("C/4",
    "11RL", "L16P15"), e só se estiver escrita. O catálogo do papel se contradiz
    (quantidade 4 E embalagem 4). Sem contagem → fora.
  * compra a peso (KG) nunca entra; monitor acompanhado (freezer) não tem referência.

A referência é a mediana do último ano; o destaque é forte quando a oferta, JÁ
COM FRETE, sai pelo menos `limiar` abaixo dela, e fraco quando só o produto sai
— o cupom é de loja física, sem frete, e o monitor compara entregue.
"""
from __future__ import annotations

import ssl
import statistics
from datetime import date, timedelta

from .base import RAIZ
from .filtros import filtro_por_regras
from .unidades import quantidade, quantidade_explicita, volume_ml

CA = RAIZ / "certificados" / "supabase-prod-ca-2021.crt"
LIMIAR_PADRAO = 0.10
CAMPOS = ("data_emissao", "descricao", "quantidade", "unidade", "valor_unitario", "valor_total", "produto",
          "produto_quantidade", "produto_unidade", "embalagem", "quantidade_base", "unidade_base", "conceito_id")


def ler_compras(aug: dict) -> list[dict]:
    """As compras da casa, pela view. Levanta exceção se não conectar: quem chama avisa."""
    import pg8000.native as pg
    con = pg.Connection(aug["usuario"], host=aug["host"], port=int(aug.get("porta", 5432)),
                        database=aug.get("banco", "postgres"), password=aug["senha"],
                        ssl_context=ssl.create_default_context(cafile=str(CA)), timeout=20)
    try:
        linhas = con.run("select " + ", ".join(CAMPOS) + " from monitor.compras_da_casa")
    finally:
        con.close()
    return [dict(zip(CAMPOS, l)) for l in linhas]


def unidade_do_monitor(cfg: dict) -> str | None:
    if cfg.get("modo") != "descoberta":
        return None
    return "litro" if (cfg.get("regras") or {}).get("volume_ml") else "unidade"


def _num(v):
    return None if v is None else float(v)


def preco_por_unidade(c: dict, unidade: str) -> float | None:
    """Preço de uma compra na unidade do monitor, ou None se não dá para afirmar."""
    if str(c.get("unidade") or "").lower() in ("kg", "g"):
        return None  # a peso
    preco = _num(c.get("valor_unitario"))
    if not preco:
        return None
    if unidade == "litro":
        base = _num(c.get("quantidade_base"))
        if not base or str(c.get("unidade_base") or "").lower() != "ml":
            return None  # catálogo sem medida: o texto do cupom não é confiável para volume
        return preco / (base / 1000)
    n = quantidade_explicita(c.get("descricao") or "")
    return preco / n if n else None


def casa_com_o_monitor(c: dict, cfg: dict) -> bool:
    """As palavras do monitor sobre o nome do catálogo + o texto do cupom; e o volume de UMA unidade."""
    regras = dict(cfg.get("regras") or {})
    faixa = regras.pop("volume_ml", None)
    regras.pop("montar_pack", None)
    regras.pop("quantidade", None)
    if not filtro_por_regras(regras)(f"{c.get('produto') or ''} {c.get('descricao') or ''}"):
        return False
    if faixa:
        base, emb = _num(c.get("quantidade_base")), _num(c.get("embalagem")) or 1
        if not base or not faixa[0] <= base / emb <= faixa[1]:
            return False
    return True


def referencia(compras: list[dict], cfg: dict, hoje: date | None = None, dias: int = 365) -> dict | None:
    unidade = unidade_do_monitor(cfg)
    if not unidade:
        return None
    hoje = hoje or date.today()
    pontos = []
    for c in compras:
        d = c["data_emissao"]
        d = d.date() if hasattr(d, "date") else date.fromisoformat(str(d)[:10])
        if d < hoje - timedelta(days=dias) or not casa_com_o_monitor(c, cfg):
            continue
        ppu = preco_por_unidade(c, unidade)
        if ppu:
            pontos.append((d, ppu, c.get("conceito_id"), c.get("descricao")))
    if not pontos:
        return None
    pontos.sort()
    return {"unidade": unidade, "mediana": round(statistics.median(p[1] for p in pontos), 4),
            "minimo": round(min(p[1] for p in pontos), 4), "compras": len(pontos),
            "ultima": pontos[-1][0].isoformat(), "conceito_id": str(pontos[-1][2] or ""),
            "limiar": float(cfg.get("limiar_augustinus", LIMIAR_PADRAO))}


def unidades_da_oferta(oferta: dict, cfg: dict, unidade: str) -> float | None:
    """Quantos litros (ou unidades) a oferta entrega — na mesma conta do relatório."""
    pack = (cfg.get("regras") or {}).get("montar_pack")
    if unidade == "litro":
        v = volume_ml(oferta["produto"])
        if not v:
            return None
        return (pack or quantidade(oferta["produto"])) * v / 1000
    return pack or quantidade(oferta["produto"])


def comparar(oferta: dict, ref: dict | None, cfg: dict) -> dict | None:
    """{"nivel": "forte"|"fraco", "com_frete", "so_produto", "mediana"} ou None."""
    if not ref or not oferta:
        return None
    n = unidades_da_oferta(oferta, cfg, ref["unidade"])
    if not n:
        return None
    alvo = ref["mediana"] * (1 - ref["limiar"])
    so_produto = (oferta.get("preco_pix") or oferta.get("preco") or 0) / n
    com_frete = oferta["total_pix"] / n if oferta.get("frete") is not None and oferta.get("total_pix") else None
    if com_frete is not None and com_frete <= alvo:
        nivel = "forte"
    elif so_produto <= alvo:
        nivel = "fraco"
    else:
        return None
    return {"nivel": nivel, "com_frete": com_frete, "so_produto": so_produto, "mediana": ref["mediana"]}
