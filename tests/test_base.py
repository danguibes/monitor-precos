"""Utilidades comuns: números brasileiros, filtros e a montagem da oferta."""
from precos.base import brl, num, oferta, prazo_legivel
from precos.filtros import criar_filtro, eh_freezer, voltagem_ok


def test_numeros_em_formato_brasileiro():
    assert num("2.879,10") == 2879.10
    assert num("49,90") == 49.90
    assert num(None) is None
    assert brl(2879.1) == "R$ 2.879,10"
    assert brl(None) == "—"


def test_prazo_da_vtex_vira_texto():
    assert prazo_legivel("4bd") == "4 dias úteis"
    assert prazo_legivel("2d") == "2 dias"
    assert prazo_legivel("até sexta") == "até sexta"


def test_voltagem():
    assert voltagem_ok("Freezer 127V", "127")
    assert not voltagem_ok("Freezer 220V", "127")
    assert voltagem_ok("Freezer Bivolt", "220")
    assert voltagem_ok("Freezer sem voltagem no título", "127")


def test_filtro_descarta_garantia_e_acessorio():
    assert not eh_freezer("GARANTIA ESTENDIDA Freezer FEI27T")
    assert not eh_freezer("Cesto para freezer")
    filtro = criar_filtro({"voltagem": "127"})
    prod = {"padrao": "FEI27T"}
    assert filtro("Freezer Vertical Electrolux FEI27T 127V", prod)
    assert not filtro("Freezer Vertical Electrolux FEI23T 127V", prod)


def test_oferta_sem_frete_nao_soma_total():
    o = oferta("Loja", "M", "Produto", "", 1000.0, 950.0, None, "", "link", "2026-10-30 10:00")
    assert o["total_pix"] == 950.0
    assert o["prazo"] == "frete não informado"
    o = oferta("Loja", "M", "Produto", "", 1000.0, 950.0, 50.0, "", "link", "2026-10-30 10:00")
    assert (o["total_pix"], o["total_cartao"]) == (1000.0, 1050.0)
