"""Amazon: leitura dos cards reais da busca (31/10/2026, já com o CEP de casa no cabeçalho).

As fixtures não têm CEP nem endereço: o cabeçalho não é gravado, só os cards.
"""
import json
from pathlib import Path

import pytest

from precos.lojas.amazon import ler_card

FIX = Path(__file__).parent / "fixtures" / "amazon"


def card(busca, trecho_titulo):
    for it in json.loads((FIX / f"busca-{busca}.json").read_text(encoding="utf-8")):
        if trecho_titulo in it["titulo"]:
            return ler_card(it["titulo"], it["texto"])
    raise AssertionError(f"card '{trecho_titulo}' não está na fixture {busca}")


def test_amazon_frete_gratis_incondicional_vale_zero():
    assert card("agua-com-gas", "Kit 6 Água Crystal Com Gás 1,5L") == \
        {"pix": 35.90, "cartao": 35.90, "frete": 0.0, "prazo": "qui., 5 de nov."}


def test_amazon_frete_pago_e_prazo():
    d = card("agua-com-gas", "Água Mineral Minalba Com Gás 1,5L")
    assert (d["pix"], d["frete"], d["prazo"]) == (4.70, 13.25, "9 - 10 de nov.")


@pytest.mark.parametrize("busca, titulo", [
    ("agua-com-gas", "íbira Água Mineral Natural Pack com 6"),          # "no seu primeiro pedido"
    ("agua-com-gas", "Agua Mineral Crystal Com Gas Pet"),              # "com o Prime"
])
def test_amazon_frete_gratis_condicional_nao_e_frete_zero(busca, titulo):
    """Grátis só no primeiro pedido ou com Prime: tratar como zero seria outro alarme falso."""
    assert card(busca, titulo)["frete"] is None


def test_amazon_cartao_vem_das_parcelas_e_nao_do_preco_riscado():
    d = card("freezer", "Freezer Horizontal Electrolux HB250")
    assert d["pix"] == 1598.98
    assert d["cartao"] == 1776.60  # 12 × R$ 148,05 — e não os R$ 2.299,00 riscados
    assert d["frete"] == 152.45


def test_amazon_cartao_explicito_no_card():
    assert card("agua-com-gas", "íbira Água Mineral Natural Pack com 6")["cartao"] == 37.90


def test_amazon_card_sem_preco_nao_vira_oferta():
    assert card("papel-higienico", "Personal Papel Higiênico Vip Folha Tripl") is None


def test_amazon_indisponivel_nao_vira_oferta():
    assert ler_card("X", "Água X\nR$ 10,00\nAtualmente indisponível.\n") is None
