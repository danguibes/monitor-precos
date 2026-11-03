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


# Peça e acessório trazem o modelo no título ("Termostato Freezer Consul Cvu20 Cvu18", visto em 31/10)
_PECA = re.compile(r"garantia|cesto|capa|pe[çc]a|borracha|termostato|resist[eê]ncia|gaxeta|prateleira|puxador"
                   r"|dobradi[çc]a|sensor|placa|timer|interruptor|ventilador", re.I)
# Peça que COMEÇA pelo nome da peça ("Tampa Do Gaveta Freezer Vertical Consul Cvu18", R$ 45,49, era o
# melhor freezer em 01/11; "Conjunto Relé De Partida Freezer"). Só no começo: "4 Gavetas" e
# "Compressor Inverter" estão no meio do título de freezer de verdade.
_PECA_NO_INICIO = re.compile(r"^\W*(tampa|conjunto|rel[eé]|kit|bandeja|gaveta|porta|p[eé]s?|motor|compressor"
                             r"|filtro|l[aâ]mpada|capacitor|cabo|suporte|organizador|pezinho|rod[ií]zio)\b", re.I)


def eh_freezer(nome: str) -> bool:
    n = nome.lower()
    return ("freezer" in n or "congelador" in n) and not _PECA.search(n) and not _PECA_NO_INICIO.search(n)


def filtro_por_regras(regras: dict):
    """Filtro do modo descoberta: busca aberta, e o anúncio passa se cumprir as regras.

    regras = {"incluir": [regex, ...]   -> todas precisam aparecer
              "excluir": [regex, ...]   -> nenhuma pode aparecer
              "volume_ml": [min, max]   -> volume de uma unidade
              "peso_g": [min, max]      -> peso de uma unidade (compara por kg)
              "quantidade": [min, max]  -> unidades no anúncio
              "montar_pack": N}         -> as unidades do anúncio precisam compor N
                                           (com N=6: avulsa, kit de 2, de 3 ou de 6)
    """
    from .unidades import peso_g, quantidade, volume_ml
    incluir = [re.compile(r, re.I) for r in regras.get("incluir", [])]
    excluir = [re.compile(r, re.I) for r in regras.get("excluir", [])]
    vol = regras.get("volume_ml")
    peso = regras.get("peso_g")
    qtd = regras.get("quantidade")
    pack = regras.get("montar_pack")

    def filtro(texto: str, prod: dict | None = None) -> bool:
        if not all(r.search(texto) for r in incluir) or any(r.search(texto) for r in excluir):
            return False
        if vol:
            v = volume_ml(texto)
            if v is None or not vol[0] <= v <= vol[1]:
                return False
        if peso:
            g = peso_g(texto)
            if g is None or not peso[0] <= g <= peso[1]:
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
