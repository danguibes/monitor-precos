"""Quantidade e volume a partir do título do anúncio, para comparar por litro.

"Água Mineral com Gás CRYSTAL Garrafa 1,5 Litros - com 6 Unidades" -> 6 × 1500 ml.
Sem indicação de quantidade, o anúncio é de uma unidade.
"""
from __future__ import annotations

import re

# A ordem importa: a contagem do que se compara (unidades, rolos, lenços) vem antes
# da do embrulho (kit, pack, fardo). "Kit 3 Pacotes ... 150 Unidades" são 150, não 3.
_QTD = [
    r"\bleve\s+(\d{1,3})\s+pague\b",  # "Leve 16 Pague 15": vêm 16
    r"\bl\s?(\d{1,3})\s?p\s?\d{1,3}\b",  # cupom fiscal: "L16P15", "L12 P11" = leve 16 (12), pague 15 (11)
    r"\bc(\d{1,3})(?=\s|$)",           # cupom fiscal: "Neve 30mts C4" = com 4
    r"\b(\d{1,3})\s*rls?\b",           # cupom fiscal: "11RL" = 11 rolos
    r"\bcom\s+(\d{1,4})\s+(?:unidades?|rolos?|latas?|len[çc]os|toalh(?:as|inhas))\b",
    r"\b(\d{1,3})\s*(?:rolos?|latas)\b",  # papel higiênico, refrigerante
    # "Completa192 Unidades": colado na palavra, sem fronteira antes do número
    r"(?<!\d)(\d{1,4})\s*(?:unidades|unids?\.?|un\.?|garrafas|len[çc]os|toalh(?:as|inhas)|panos)(?=\W|$)",
    r"\bc/\s*(\d{1,4})\b",
    r"\bkit\s+(?:c/\s*|com\s+)?(\d{1,3})\b",
    r"\b(?:pack|fardo|caixa|cx\.?|pct\.?|pacote|engradado)\s*(?:c/\s*|com\s+|de\s+)?(\d{1,3})\b",
    r"\b(\d{1,3})\s*x\s*\d",  # 6x1,5L
    r"\b(\d{1,4})\s*(?:folhas|fls)\b",  # lenço umedecido: "Pacote 16 Folhas" (por último: papel tem "folha dupla")
]
# Kit, combo ou "N pacotes": a contagem pode ser do kit inteiro ou de cada pacote, e o
# título não diz qual. Vale a do título sem multiplicar — o menor total, que nunca faz
# o kit parecer mais barato do que é —, e a página marca a oferta para conferir.
_KIT = re.compile(r"\bkit\b|\bcombo\b|\b\d{1,2}\s*(?:pacotes|pcts?\b\.?|embalagens)")
_VOL = re.compile(r"(\d+(?:[.,]\d+)?)\s*(ml|litros?|lts?|l)(?![a-z])", re.I)


def quantidade_explicita(titulo: str) -> int | None:
    """A contagem escrita no título, ou None se não há nenhuma (não presume 1)."""
    t = titulo.lower()
    for padrao in _QTD:
        m = re.search(padrao, t)
        if m and 0 < int(m.group(1)) <= 1000:
            return int(m.group(1))
    return None


def kit_ambiguo(titulo: str) -> bool:
    """Anúncio de kit com contagem: pode ser o total ou por pacote. A página pede para conferir."""
    return bool(_KIT.search(titulo.lower())) and quantidade_explicita(titulo) is not None


def quantidade(titulo: str) -> int:
    """Sem contagem no título, o anúncio é de uma unidade."""
    return quantidade_explicita(titulo) or 1


def volume_ml(titulo: str) -> float | None:
    """Volume de uma unidade, em ml. O primeiro volume do título vale."""
    m = _VOL.search(titulo)
    if not m:
        return None
    v = float(m.group(1).replace(",", "."))
    if m.group(2).lower() == "ml":
        # "C/gas 1,5ml" é erro de digitação de 1,5 L (visto no Hirota); ml com decimal abaixo de 10 não existe
        return v * 1000 if v < 10 and re.search(r"[.,]", m.group(1)) else v
    return v * 1000


def montar_pack(o: dict, pack: int) -> dict | None:
    """Converte a oferta no custo de levar `pack` unidades: 6 avulsas, 2 kits de 3...

    O preço multiplica e o frete entra uma vez só. None se as unidades do
    anúncio não compõem o pack (um kit de 4 não vira 6).
    """
    q = quantidade(o["produto"])
    if pack % q:
        return None
    f = pack // q
    if f == 1:
        return o
    o = dict(o)
    for c in ("preco", "preco_pix"):
        o[c] = round(o[c] * f, 2) if o[c] is not None else None
    frete = o["frete"] or 0
    o["total_pix"] = round((o["preco_pix"] or 0) + frete, 2) if o["preco_pix"] is not None else None
    o["total_cartao"] = round((o["preco"] or 0) + frete, 2) if o["preco"] is not None else None
    if o["frete"] is None:
        o["total_pix"], o["total_cartao"] = o["preco_pix"], o["preco"]
    o["produto"] = f"{f} × {o['produto']}"
    return o


def unidade_de_comparacao(cfg: dict) -> str | None:
    """"litro" (o monitor tem volume_ml), "unidade" (o resto) ou None (monitor acompanhado, como o freezer)."""
    if cfg.get("modo") != "descoberta":
        return None
    return "litro" if (cfg.get("regras") or {}).get("volume_ml") else "unidade"


def sufixo(cfg: dict) -> str:
    return "/L" if unidade_de_comparacao(cfg) == "litro" else "/" + cfg.get("unidade_nome", "un.")


def unidades_na_oferta(produto: str, cfg: dict) -> float | None:
    """Litros ou unidades que a oferta entrega; None se o título não diz.

    Com montar_pack o anúncio já foi convertido no pack inteiro. Sem ele, a
    contagem precisa estar ESCRITA no título: pacotes de 16, 20 e 50 lenços só
    se comparam por unidade, e "sem número" não pode virar 1.
    """
    pack = (cfg.get("regras") or {}).get("montar_pack")
    if unidade_de_comparacao(cfg) == "litro":
        v = volume_ml(produto)
        if not v:
            return None
        return (pack or quantidade(produto)) * v / 1000
    return pack or quantidade_explicita(produto)


def litros(titulo: str) -> float | None:
    v = volume_ml(titulo)
    return None if v is None else round(quantidade(titulo) * v / 1000, 3)
