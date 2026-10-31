"""Quantidade e volume a partir do título do anúncio, para comparar por litro.

"Água Mineral com Gás CRYSTAL Garrafa 1,5 Litros - com 6 Unidades" -> 6 × 1500 ml.
Sem indicação de quantidade, o anúncio é de uma unidade.
"""
from __future__ import annotations

import re

_QTD = [
    r"\bleve\s+(\d{1,3})\s+pague\b",  # "Leve 16 Pague 15": vêm 16
    r"\bl\s?(\d{1,3})\s?p\s?\d{1,3}\b",  # cupom fiscal: "L16P15", "L12 P11" = leve 16 (12), pague 15 (11)
    r"\bc(\d{1,3})(?=\s|$)",           # cupom fiscal: "Neve 30mts C4" = com 4
    r"\b(\d{1,3})\s*rls?\b",           # cupom fiscal: "11RL" = 11 rolos
    r"\bcom\s+(\d{1,3})\s+(?:unidades?|rolos?|latas?)\b",
    r"\b(\d{1,3})\s*(?:rolos?|latas)\b",  # papel higiênico, refrigerante
    r"\bkit\s+(?:c/\s*|com\s+)?(\d{1,3})\b",
    r"\b(?:pack|fardo|caixa|cx\.?|pct\.?|pacote|engradado)\s*(?:c/\s*|com\s+|de\s+)?(\d{1,3})\b",
    r"\bc/\s*(\d{1,3})\b",
    r"\b(\d{1,3})\s*(?:unidades|unids?\.?|un\.?|garrafas)(?=\W|$)",
    r"\b(\d{1,3})\s*x\s*\d",  # 6x1,5L
    r"\b(\d{1,3})\s*(?:folhas|fls)\b",  # lenço umedecido: "Pacote 16 Folhas" (por último: papel tem "folha dupla")
]
# "Kit 4 Pacotes com 48 Unidades" são 192 unidades, não 4 nem 48
_PACOTES = re.compile(r"\b(?:kit\s+(?:c/\s*|com\s+)?)?(\d{1,2})\s*(?:pacotes|pcts?\.?|embalagens)\b")
_VOL = re.compile(r"(\d+(?:[.,]\d+)?)\s*(ml|litros?|lts?|l)(?![a-z])", re.I)


def quantidade_explicita(titulo: str) -> int | None:
    """A contagem escrita no título, ou None se não há nenhuma (não presume 1)."""
    t = titulo.lower()
    m = _PACOTES.search(t)
    if m:  # N pacotes × a contagem de dentro de cada um, procurada no resto do título
        dentro = quantidade_explicita(t[:m.start()] + " " + t[m.end():])
        if dentro and dentro != int(m.group(1)):
            return int(m.group(1)) * dentro
    for padrao in _QTD:
        m = re.search(padrao, t)
        if m and 0 < int(m.group(1)) <= 200:
            return int(m.group(1))
    return None


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
