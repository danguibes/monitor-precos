"""Quantidade e volume no título, e as regras do monitor de água com gás.

Os títulos são reais, copiados de Pão de Açúcar, Carrefour, Mambo, Atacadão e Oba em 30/10/2026.
"""
import tomllib
from pathlib import Path

import pytest

from precos.filtros import filtro_por_regras
from precos.base import oferta
from precos.unidades import litros, montar_pack, quantidade, volume_ml

AGUA = tomllib.loads((Path(__file__).parent.parent / "monitores" / "agua-com-gas.toml").read_text(encoding="utf-8"))


@pytest.mark.parametrize("titulo, qtd, ml", [
    ("Água Mineral com Gás CRYSTAL Garrafa 1,5 Litros - com 6 Unidades", 6, 1500),
    ("Água Mineral com Gás MINALBA Garrafa 1,5 Litros - com 12 Unidades", 12, 1500),
    ("Água Mineral com Gás BIOLEVE Garrafa 1,5 Litro", 1, 1500),
    ("Kit 6 Água Mineral Igarapé 1,5 Litro", 6, 1500),
    ("Kit 3 Água Mineral Crystal Gasosa 1,5 Litros", 3, 1500),
    ("Água Mineral sem Gás Prata 1,5L", 1, 1500),
    ("Água com Gás Smart Balance 330ml", 1, 330),
    ("Água Mineral São Lourenço com Gás 6x1,5L", 6, 1500),
    ("Água Mineral com Gás Pack c/6 1.5 L", 6, 1500),
    ("Água Mineral com Gás Fardo 6 Garrafas 1,5l", 6, 1500),
    ("Água Mineral Crystal sem Gás 5l", 1, 5000),
    ("Agua Min. Casa De Mae C/gas 1,5ml", 1, 1500),  # erro de digitação do Hirota
    ("Agua Min. Casa De Mae C/gas 510ml", 1, 510),
])
def test_quantidade_e_volume(titulo, qtd, ml):
    assert quantidade(titulo) == qtd
    assert volume_ml(titulo) == ml


@pytest.mark.parametrize("titulo, qtd", [
    # formatos de título de papel higiênico; "12 Rolos" era lido como 1 unidade
    ("Papel Higiênico Folha Dupla Neve 12 Rolos 30m", 12),
    ("Papel Higiênico Personal Folha Dupla 30m com 12 Rolos", 12),
    ("Papel Higiênico Folha Tripla Leve 16 Pague 15", 16),
    ("Papel Higiênico Folha Dupla 4 Rolos 30m", 4),
    ("Papel Higiênico Folha Dupla Pacote com 12 Unidades", 12),
    ("Papel Higiênico Folha Simples 1 Rolo 300m", 1),
    ("Refrigerante Guaraná 350ml 12 latas", 12),
    # como os cupons fiscais abreviam (descrições reais do Augustinus)
    ("PAPEL HIG NEVE F DUPLA 30M C/4 NEUTRO", 4),
    ("PAPEL HIG MIMO F DUPLA 30M L16P15", 16),
    ("PAPEL HIGIENNEVE 11RL", 11),
    ("P H MAX 30M L12 P11", 12),
    ("Neve 30mts C4", 4),
    ("PH MAX PURE 30M C/40", 40),
])
def test_quantidade_em_rolos_latas_e_leve_pague(titulo, qtd):
    assert quantidade(titulo) == qtd




def test_litros_do_pack():
    assert litros("Água Mineral com Gás CRYSTAL Garrafa 1,5 Litros - com 6 Unidades") == 9.0
    assert litros("Água sem indicação de volume") is None


@pytest.mark.parametrize("titulo, passa", [
    ("Água Mineral com Gás CRYSTAL Garrafa 1,5 Litros - com 6 Unidades", True),
    ("Água Mineral com Gás MINALBA Garrafa 1,5 Litros - com 6 Unidades", True),
    ("Água Mineral com Gás MINALBA Garrafa 1,5 Litros - com 12 Unidades", False),  # passa de 6
    ("Água Mineral com Gás BIOLEVE Garrafa 1,5 Litro", True),  # avulsa: 6 delas fazem o pack
    ("Kit 3 Água Mineral Crystal Gasosa 1,5 Litros", True),  # 2 kits de 3
    ("Kit de Água Mineral Oba Bem Querer Natural Com Gás 1.5l - 12 unidades", False),
    ("Água Mineral com Gás Prata 1,27L", False),
    ("Água Mineral sem Gás MINALBA Garrafa 1,5 Litros - com 6 Unidades", False),
    ("Kit 6 Água Mineral Igarapé 1,5 Litro", False),  # não diz que é com gás
    ("Água Mineral com Gás MINALBA 510ml - com 12 Unidades", False),
    ("Água Mineral São Lourenço com Gás 6x1,5L", True),
    ("Água com Gás Sabor Limonada Efferv 1,5L c/6", False),
    ("Combo 1 Aperitivo Aperol 750ml + 1 Água Crystal Com Gás PET 1,5L", False),
])
def test_regras_do_monitor_agua_com_gas(titulo, passa):
    assert filtro_por_regras(AGUA["regras"])(titulo) is passa


def test_montar_pack_soma_o_produto_e_cobra_o_frete_uma_vez():
    avulsa = oferta("Mambo", "M", "Água Mineral com Gás Minalba Pet 1,5L", "", 5.49, None, 12.9, "2 h", "x", "d")
    o = montar_pack(avulsa, 6)
    assert o["produto"] == "6 × Água Mineral com Gás Minalba Pet 1,5L"
    assert (o["preco"], o["total_pix"]) == (32.94, 45.84)
    kit3 = oferta("Carrefour", "M", "Kit 3 Água Mineral Crystal Gasosa 1,5 Litros", "", 12.57, 11.69, 20.99, "", "x", "d")
    assert montar_pack(kit3, 6)["total_pix"] == round(2 * 11.69 + 20.99, 2)
    pack6 = oferta("PA", "M", "Água com Gás CRYSTAL 1,5 Litros - com 6 Unidades", "", 28.14, None, 19.9, "", "x", "d")
    assert montar_pack(pack6, 6) is pack6
    kit4 = oferta("X", "M", "Kit 4 Água com Gás 1,5L", "", 20.0, None, 0.0, "", "x", "d")
    assert montar_pack(kit4, 6) is None


import pytest as _pt
from precos.unidades import quantidade_explicita as _qe, unidades_na_oferta as _uno


@_pt.mark.parametrize("titulo, n", [
    ("Lenço Umedecido Neve Care On The Go Pacote 16 Folhas", 16),
    ("Toalha Umedecida Cotondela Baby 50 un", 50),
    ("Lenço Umedecido Huggies Tripla Proteção - 88 Unidades", 88),
    ("Kit 4 Pacotes Lenço Umedecido Huggies com 48 Unidades", 48),   # total ou por pacote? o menor
    ("Kit 3 Pacotes de Toalhas Umedecidas Lenço Umedecido Geriátrica 150 Unidades", 150),  # visto em 31/10
    ("Lenço Umedecido Use It Balde Azul Com 400 Unidades", 400),
    ("Lenços Umedecidos Pampers Higiene Completa192 Unidades", 192),
    ("Toalhinhas Umed Premium 1 Unidade Com 120 Lenços Umedecidos", 120),
    ("Kit 400 Lenço Umedecido Kit Toalhas Umedecidas Bebe", 400),
    ("Meu Bebê Ultra Toalhas Umedecidas, Hygieline, 500 Folhas", 500),
    ("Papel Higiênico Folha Dupla Neve 12 Rolos", 12),       # "folha dupla" não é contagem
    ("Lenço Umedecido Huggies", None),
])
def test_contagem_de_lencos(titulo, n):
    assert _qe(titulo) == n


def test_unidades_na_oferta_por_monitor():
    lenco = {"modo": "descoberta", "regras": {"incluir": [], "excluir": []}}
    assert _uno("Toalha Umedecida 50 un", lenco) == 50 and _uno("Lenço Umedecido Huggies", lenco) is None
    agua = {"modo": "descoberta", "regras": {"volume_ml": [1400, 1600], "montar_pack": 6}}
    assert _uno("Água com Gás 1,5L", agua) == 9.0
    papel = {"modo": "descoberta", "regras": {"montar_pack": 12}}
    assert _uno("2 × Papel Higiênico 6 Rolos", papel) == 12


from precos.unidades import kit_ambiguo as _kit


@_pt.mark.parametrize("titulo, ambiguo", [
    ("Kit 3 Pacotes de Toalhas Umedecidas 150 Unidades", True),
    ("Lenço Umedecido Pampers 3 pacotes 48 unidades", True),
    ("Combo Lenço Umedecido Huggies 2x48 Unidades", True),
    ("Toalha Umedecida Cotondela Baby 50 un", False),
    ("Kit Toalha Umedecida", False),                         # sem contagem já não entra na conta
])
def test_kit_pede_conferencia(titulo, ambiguo):
    assert _kit(titulo) is ambiguo


def test_etiqueta_de_kit_no_relatorio():
    from precos.relatorio import aviso_kit
    lenco = {"modo": "descoberta", "regras": {"incluir": [], "excluir": []}, "por_unidade": True}
    etiqueta = aviso_kit("Kit 3 Pacotes de Toalhas Umedecidas 150 Unidades", lenco)
    assert "confira a quantidade" in etiqueta and "contei 150 no total" in etiqueta
    assert aviso_kit("Toalha Umedecida Cotondela Baby 50 un", lenco) == ""
    assert aviso_kit("Kit 3 Pacotes 150 Unidades", {"modo": "acompanhado"}) == ""   # freezer não conta unidades



def test_sem_volume_pack_ou_por_unidade_compara_pelo_total(tmp_path):
    """Em 01/11 celular e colchão ficaram sem melhor oferta: viravam "por unidade" sem contagem no título."""
    from precos.historico import gravar_historico
    from precos.relatorio import analisar
    from precos.historico import ler_historico
    from precos.base import oferta
    from precos.unidades import unidade_de_comparacao
    celular = {"modo": "descoberta", "titulo": "x", "termos": ["x"], "regras": {"incluir": [], "excluir": []}}
    assert unidade_de_comparacao(celular) is None
    assert unidade_de_comparacao(dict(celular, por_unidade=True)) == "unidade"
    assert unidade_de_comparacao(dict(celular, regras={"montar_pack": 12})) == "unidade"
    assert unidade_de_comparacao(dict(celular, regras={"volume_ml": [900, 1100]})) == "litro"
    arq = tmp_path / "h.csv"
    gravar_historico([oferta("ML", "ML", "Xiaomi 17t 5g 512gb Global", "v", 4299.14, 4299.14, 0.0, "", "l", "2026-11-01 16:19"),
                      oferta("ML", "ML", "Xiaomi 17t 512gb 12gb Ram", "v", 4499.0, 4499.0, 0.0, "", "l2", "2026-11-01 16:19")], arq)
    _, res = analisar(ler_historico(arq), celular)
    assert res[0]["melhor"]["total_pix"] == 4299.14
