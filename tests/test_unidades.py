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
