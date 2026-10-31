"""Histórico em CSV, separado por ';' e com vírgula decimal (abre direto no Excel)."""
from __future__ import annotations

import csv

from .base import HISTORICO

CAMPOS = ["data", "loja", "modelo", "produto", "sku", "vendedor", "preco",
          "preco_pix", "frete", "prazo", "total_pix", "total_cartao", "link"]
NUMERICOS = ("preco", "preco_pix", "frete", "total_pix", "total_cartao")


# Linhas gravadas por defeitos já corrigidos. Não se apagam do CSV (o registro do
# que o monitor viu fica): são descartadas na leitura, com o motivo à vista na
# página de histórico. Regra nova entra aqui, com data e motivo.
DESCARTES = [
    ("frete igual ao preço do produto — o Magalu lia o \"Enviar para\" da barra do topo "
     "(corrigido em 30/10)",
     lambda l: bool(l["frete"]) and l["frete"] in (l["preco"], l["preco_pix"])),
    ("Atacadão consultado pelo vendedor genérico, e não pela loja física do CEP — oferta "
     "que o site não vendia (corrigido em 31/10, 13:00)",
     lambda l: l["loja"] == "Atacadão" and l["data"] < "2026-10-31 13:00"),
]


def descartar(linhas):
    """(linhas boas, {motivo: quantas descartadas})."""
    boas, contagem = [], {}
    for l in linhas:
        motivo = next((m for m, regra in DESCARTES if regra(l)), None)
        if motivo:
            contagem[motivo] = contagem.get(motivo, 0) + 1
        else:
            boas.append(l)
    return boas, contagem


def ler_historico(caminho=HISTORICO, bruto=False):
    """As linhas do CSV, já sem as de DESCARTES (bruto=True devolve tudo)."""
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
    return linhas if bruto else descartar(linhas)[0]


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
