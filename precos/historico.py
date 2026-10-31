"""Histórico em CSV, separado por ';' e com vírgula decimal (abre direto no Excel)."""
from __future__ import annotations

import csv

from .base import HISTORICO

CAMPOS = ["data", "loja", "modelo", "produto", "sku", "vendedor", "preco",
          "preco_pix", "frete", "prazo", "total_pix", "total_cartao", "link"]
NUMERICOS = ("preco", "preco_pix", "frete", "total_pix", "total_cartao")


def ler_historico(caminho=HISTORICO):
    if not caminho.exists():
        return []
    with caminho.open(encoding="utf-8-sig", newline="") as f:
        linhas = list(csv.DictReader(f, delimiter=";"))
    for l in linhas:
        for c in NUMERICOS:
            try:
                l[c] = float(str(l[c]).replace(",", "."))
            except (ValueError, TypeError):
                l[c] = None
    return linhas


def gravar_historico(ofertas, caminho=HISTORICO):
    caminho.parent.mkdir(exist_ok=True)
    novo = not caminho.exists()
    with caminho.open("a", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=CAMPOS, delimiter=";")
        if novo:
            w.writeheader()
        for o in ofertas:
            linha = dict(o)
            for c in NUMERICOS:
                linha[c] = "" if o[c] is None else f"{o[c]:.2f}".replace(".", ",")
            w.writerow(linha)
