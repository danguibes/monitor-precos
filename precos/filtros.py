"""Decide se um anúncio pertence a um modelo acompanhado."""
from __future__ import annotations

import re


def voltagem_ok(texto: str, preferida: str) -> bool:
    t = texto.lower()
    if "bivolt" in t:
        return True
    tem_110 = bool(re.search(r"\b(110|127)\s*v?\b", t))
    tem_220 = bool(re.search(r"\b220\s*v?\b", t))
    if not tem_110 and not tem_220:
        return True  # anúncio não diz a voltagem: mantém
    if preferida in ("110", "127"):
        return tem_110
    if preferida == "220":
        return tem_220
    return True


def eh_freezer(nome: str) -> bool:
    n = nome.lower()
    return (("freezer" in n or "congelador" in n) and "garantia" not in n
            and "cesto" not in n and "capa" not in n and "peça" not in n and "borracha" not in n)


def filtro_por_regras(regras: dict):
    """Filtro do modo descoberta: busca aberta, e o anúncio passa se cumprir as regras.

    regras = {"incluir": [regex, ...]   -> todas precisam aparecer
              "excluir": [regex, ...]   -> nenhuma pode aparecer
              "volume_ml": [min, max]   -> volume de uma unidade
              "quantidade": [min, max]  -> unidades no anúncio
              "montar_pack": N}         -> as unidades do anúncio precisam compor N
                                           (com N=6: avulsa, kit de 2, de 3 ou de 6)
    """
    from .unidades import quantidade, volume_ml
    incluir = [re.compile(r, re.I) for r in regras.get("incluir", [])]
    excluir = [re.compile(r, re.I) for r in regras.get("excluir", [])]
    vol = regras.get("volume_ml")
    qtd = regras.get("quantidade")
    pack = regras.get("montar_pack")

    def filtro(texto: str, prod: dict | None = None) -> bool:
        if not all(r.search(texto) for r in incluir) or any(r.search(texto) for r in excluir):
            return False
        if vol:
            v = volume_ml(texto)
            if v is None or not vol[0] <= v <= vol[1]:
                return False
        if qtd and not qtd[0] <= quantidade(texto) <= qtd[1]:
            return False
        if pack and pack % quantidade(texto):
            return False
        return True
    return filtro


def criar_filtro(cfg):
    if cfg.get("regras"):
        return filtro_por_regras(cfg["regras"])
    volt = str(cfg.get("voltagem", "127"))

    def filtro(texto: str, prod: dict) -> bool:
        return (eh_freezer(texto) and re.search(prod["padrao"], texto, re.I) is not None
                and voltagem_ok(texto, volt))
    return filtro
