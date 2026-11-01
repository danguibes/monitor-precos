"""Taxa de serviço do Atacadão: 6% do subtotal, somada ao frete (três carrinhos reais de 01/11/2026)."""
import pytest

from precos.base import oferta
from precos.coleta import somar_taxa_servico, taxas_de_servico
from precos.unidades import montar_pack

ATACADAO = {"Atacadão": 0.06}


@pytest.mark.parametrize("subtotal, taxa", [(207.70, 12.46), (240.60, 14.44), (371.20, 22.27)])
def test_bate_com_os_carrinhos(subtotal, taxa):
    o = somar_taxa_servico(oferta("Atacadão", "x", "itens", "", subtotal, subtotal, 0.0, "1 dias úteis", "l", "d"), ATACADAO)
    assert o["frete"] == taxa and o["total_pix"] == round(subtotal + taxa, 2)
    assert "taxa de serviço de 6%" in o["prazo"]


def test_taxa_depois_do_pack_incide_sobre_as_seis():
    agua = oferta("Atacadão", "x", "Água Minalba Com gás 1,5L", "", 3.29, 3.29, 0.0, "", "l", "d")
    seis = somar_taxa_servico(montar_pack(agua, 6), ATACADAO)
    assert seis["preco_pix"] == 19.74 and seis["frete"] == 1.18 and seis["total_pix"] == 20.92


def test_outras_lojas_nao_mudam_e_a_taxa_vem_do_lojas_toml():
    o = oferta("Mambo", "x", "y", "", 10.0, 10.0, 5.0, "", "l", "d")
    assert somar_taxa_servico(o, ATACADAO) == o
    assert taxas_de_servico({"lojas": [{"nome": "Atacadão", "taxa_servico": 0.06}, {"nome": "Mambo"}]}) == ATACADAO
