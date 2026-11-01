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
    assert not eh_freezer("Termostato Freezer Consul Cvu20 Cvu18 W11283283 Original")
    assert not eh_freezer("Gaxeta Borracha Porta Freezer Electrolux FEI27T")
    assert not eh_freezer("Tampa Do Gaveta Freezer Vertical Consul Cvu18 Cvu20")     # o "melhor freezer" de 01/11
    assert not eh_freezer("Conjunto Relé De Partida Freezer Vertical 18 Consul Cvu18")
    assert eh_freezer("Freezer Vertical Philco 4 Gavetas 140L PFV165B")              # gaveta no meio: é freezer
    assert eh_freezer("Freezer Vertical Electrolux Fei27t 249l Compressor Inverter Branco Bivolt")
    assert eh_freezer("Freezer Vertical Degelo Manual Consul 1 Porta 121 Litros CVU18GBBNA")
    assert eh_freezer("Freezer Vertical Consul 1 Porta 254L CVU26MB")
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
