"""Referência de preço pelo Augustinus: as unidades certas, e as armadilhas que deixam a compra de fora.

As linhas imitam compras reais da casa (mesmas descrições de cupom e as mesmas
esquisitices do catálogo), sem datas nem valores que identifiquem a casa.
"""
import tomllib
from datetime import date
from pathlib import Path

import pytest

from precos.augustinus import comparar, preco_por_unidade, referencia
from precos.base import oferta

RAIZ = Path(__file__).parent.parent
AGUA = tomllib.loads((RAIZ / "monitores" / "agua-com-gas.toml").read_text(encoding="utf-8"))
PAPEL = {"modo": "descoberta", "termos": ["x"], "titulo": "x",
         "regras": {"incluir": ["p[aá]p[eé]l\\s*h[ií]g[ií][eé]n[ií][cç][oó]"], "excluir": [], "montar_pack": 12}}
HOJE = date(2026, 10, 31)


def compra(desc, preco, produto, qtd_cat=None, un_cat=None, emb=1, base=None, un_base=None, un_nota="Un", dia="2026-09-07"):
    return {"data_emissao": dia, "descricao": desc, "quantidade": 6, "unidade": un_nota, "valor_unitario": preco,
            "valor_total": preco * 6, "produto": produto, "produto_quantidade": qtd_cat, "produto_unidade": un_cat,
            "embalagem": emb, "quantidade_base": base, "unidade_base": un_base, "conceito_id": "c-agua"}


MINALBA = compra("AG MINALBA C/G 1,5LT", 3.59, "Água Mineral com Gás", 1.5, "l", 1, 1500, "ml", "Gf")
SEM_GAS = compra("AG PETROPO S/G 1,5LT", 2.79, "Água sem gás", 1.5, "l", 1, 1500, "ml")
CORTADA = compra("AGUA MINMINALBA 15L", 3.99, "Água Mineral com Gás")            # catálogo sem medida
SANITARIA = compra("AG SANIT AGIFACIL 2L", 4.19, "Água sanitária", 2, "l", 1, 2000, "ml")


def test_agua_preco_por_litro_vem_do_catalogo():
    assert round(preco_por_unidade(MINALBA, "litro"), 4) == round(3.59 / 1.5, 4)


def test_agua_cortada_no_cupom_nao_vira_15_litros():
    """'15L' é 1,5 L cortado; sem medida no catálogo, a compra fica fora em vez de dar R$ 0,27/L."""
    assert preco_por_unidade(CORTADA, "litro") is None


def test_referencia_da_agua_so_com_gas_e_so_o_que_tem_medida():
    ref = referencia([MINALBA, SEM_GAS, CORTADA, SANITARIA], AGUA, HOJE)
    assert ref["compras"] == 1 and ref["unidade"] == "litro"
    assert ref["mediana"] == round(3.59 / 1.5, 4) and ref["conceito_id"] == "c-agua"


@pytest.mark.parametrize("desc, qtd_cat, emb, preco, por_rolo", [
    ("PAPEL HIG NEVE F DUPLA 30M C/4 NEUTRO", 4, 4, 10.98, 10.98 / 4),   # catálogo diz 4 × 4: o cupom manda
    ("PAPEL HIG MIMO F DUPLA 30M L16P15", None, 16, 28.98, 28.98 / 16),  # leve 16, pague 15
    ("PAPEL HIGIENNEVE 11RL", None, None, 30.90, 30.90 / 11),
])
def test_papel_preco_por_rolo_vem_da_contagem_do_cupom(desc, qtd_cat, emb, preco, por_rolo):
    c = compra(desc, preco, "Papel Higiênico Folha Dupla", qtd_cat, "un", emb)
    assert round(preco_por_unidade(c, "unidade"), 4) == round(por_rolo, 4)


def test_papel_sem_contagem_no_cupom_fica_fora():
    assert preco_por_unidade(compra("PAPEL HIG NEVE NEUTRO", 12.0, "Papel Higiênico"), "unidade") is None


def test_compra_a_peso_nunca_entra():
    assert preco_por_unidade(compra("AG X 1,5L", 3.0, "Água", 1.5, "l", 1, 1500, "ml", un_nota="KG"), "litro") is None


def test_freezer_nao_tem_referencia():
    assert referencia([MINALBA], {"modo": "acompanhado", "produtos": []}, HOJE) is None


def test_compra_antiga_fica_fora_do_ano():
    velha = dict(MINALBA, data_emissao="2025-06-01")
    assert referencia([velha], AGUA, HOJE) is None


def test_comparar_forte_fraco_e_nada():
    ref = referencia([MINALBA], AGUA, HOJE)  # R$ 2,39/L; alvo 10% abaixo = R$ 2,15/L
    barata = oferta("Amazon", "Amazon", "Água com Gás 1,5L Fardo com 6 Unidades", "", 17.0, 17.0, 0.0, "", "x", "d")
    assert comparar(barata, ref, AGUA)["nivel"] == "forte"           # 17/9 = R$ 1,89/L entregue
    frete_come = oferta("X", "X", "Água com Gás 1,5L com 6 Unidades", "", 18.0, 18.0, 15.0, "", "x", "d")
    assert comparar(frete_come, ref, AGUA)["nivel"] == "fraco"        # produto R$ 2,00/L, entregue R$ 3,67/L
    cara = oferta("Y", "Y", "Água com Gás 1,5L com 6 Unidades", "", 30.0, 30.0, 0.0, "", "x", "d")
    assert comparar(cara, ref, AGUA) is None
    sem_frete = oferta("Z", "Z", "Água com Gás 1,5L com 6 Unidades", "", 17.0, 17.0, None, "", "x", "d")
    assert comparar(sem_frete, ref, AGUA)["nivel"] == "fraco"         # frete desconhecido nunca é "forte"
