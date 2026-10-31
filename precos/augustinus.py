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
  * a unidade é a mesma do relatório (unidades.unidade_de_comparacao): sem
    montar_pack, a oferta conta pela contagem escrita no título ("50 un",
    "16 folhas"), e a compra pela do cupom — lenço contra lenço, nunca pacote
    contra pacote. Sem regra `incluir`, a compra precisa conter todas as
    palavras de um dos termos de busca — senão a casa inteira entra (visto em
    31/10: o lenço, que a casa nunca comprou, ganhou 46 compras).

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
from .unidades import quantidade_explicita, unidade_de_comparacao, unidades_na_oferta

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


unidade_do_monitor = unidade_de_comparacao


def _palavras(t: str) -> list[str]:
    import re
    import unicodedata
    t = "".join(c for c in unicodedata.normalize("NFD", t.lower()) if unicodedata.category(c) != "Mn")
    return re.findall(r"[a-z0-9]+", t)


def casa_com_termos(texto: str, termos: list[str]) -> bool:
    """Todas as palavras (de 3+ letras) de algum termo aparecem no texto, sem acento."""
    tem = set(_palavras(texto))
    return any(ps and all(p in tem for p in ps)
               for ps in ([p for p in _palavras(t) if len(p) >= 3] for t in termos))


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
    texto = f"{c.get('produto') or ''} {c.get('descricao') or ''}"
    if not filtro_por_regras(regras)(texto):
        return False
    if not regras.get("incluir") and not casa_com_termos(c.get("produto") or "", cfg.get("termos") or []):
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
            pontos.append((d, ppu, str(c.get("conceito_id") or ""), c.get("produto") or ""))
    if not pontos:
        return None
    pontos.sort()
    return {"unidade": unidade, "mediana": round(statistics.median(p[1] for p in pontos), 4),
            "minimo": round(min(p[1] for p in pontos), 4), "compras": len(pontos),
            "ultima": pontos[-1][0].isoformat(), "conceitos": conceitos(pontos, cfg),
            "limiar": float(cfg.get("limiar_augustinus", LIMIAR_PADRAO))}


def conceitos(pontos: list[tuple], cfg: dict, limite: int = 3) -> list[dict]:
    """Os conceitos do Augustinus por trás da referência, o mais parecido com o monitor primeiro.

    A ordem não é a da compra mais recente: no papel ela caía em "Papel
    higiênico", o conceito genérico, e não em "Papel higiênico folha dupla", que
    existe e é o nome do monitor. Conta as palavras em comum, desconta as que o
    conceito tem a mais ("Neutro") e desempata pelo número de compras. Cada um
    leva a própria mediana, para a página mostrar mais de um quando houver dúvida.
    """
    alvo = set(_palavras(cfg.get("nome") or cfg.get("titulo") or ""))
    grupos: dict[str, dict] = {}
    for _, ppu, conceito, nome in pontos:
        if conceito:
            g = grupos.setdefault(conceito, {"id": conceito, "nome": nome, "precos": []})
            g["precos"].append(ppu)

    def nota(g):
        ps = set(_palavras(g["nome"]))
        return (len(ps & alvo), -len(ps - alvo), len(g["precos"]))

    return [{"id": g["id"], "nome": g["nome"], "compras": len(g["precos"]),
             "mediana": round(statistics.median(g["precos"]), 4)}
            for g in sorted(grupos.values(), key=nota, reverse=True)[:limite]]


def comparar(oferta: dict, ref: dict | None, cfg: dict) -> dict | None:
    """{"nivel": "forte"|"fraco", "com_frete", "so_produto", "mediana"} ou None."""
    if not ref or not oferta:
        return None
    n = unidades_na_oferta(oferta["produto"], cfg)
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
