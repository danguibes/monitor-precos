"""Quantidade e volume a partir do título do anúncio, para comparar por litro.

"Água Mineral com Gás CRYSTAL Garrafa 1,5 Litros - com 6 Unidades" -> 6 × 1500 ml.
Sem indicação de quantidade, o anúncio é de uma unidade.
"""
from __future__ import annotations

import re

_QTD = [
    r"\bleve\s+(\d{1,3})\s+pague\b",  # "Leve 16 Pague 15": vêm 16
    r"\bcom\s+(\d{1,3})\s+(?:unidades?|rolos?|latas?)\b",
    r"\b(\d{1,3})\s*(?:rolos?|latas)\b",  # papel higiênico, refrigerante
    r"\bkit\s+(?:c/\s*|com\s+)?(\d{1,3})\b",
    r"\b(?:pack|fardo|caixa|cx\.?|pct\.?|pacote|engradado)\s*(?:c/\s*|com\s+|de\s+)?(\d{1,3})\b",
    r"\bc/\s*(\d{1,3})\b",
    r"\b(\d{1,3})\s*(?:unidades|unids?\.?|un\.?|garrafas)(?=\W|$)",
    r"\b(\d{1,3})\s*x\s*\d",  # 6x1,5L
]
_VOL = re.compile(r"(\d+(?:[.,]\d+)?)\s*(ml|litros?|lts?|l)(?![a-z])", re.I)


def quantidade(titulo: str) -> int:
    t = titulo.lower()
    for padrao in _QTD:
        m = re.search(padrao, t)
        if m and 0 < int(m.group(1)) <= 200:
            return int(m.group(1))
    return 1


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


def litros(titulo: str) -> float | None:
    v = volume_ml(titulo)
    return None if v is None else round(quantidade(titulo) * v / 1000, 3)
