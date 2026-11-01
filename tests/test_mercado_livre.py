"""Mercado Livre: preço e frete do JSON-LD, vendedor e prazo da caixa de compra (páginas reais de 30/10/2026).

As fixtures têm o CEP de destino do JSON-LD trocado por zeros e o texto sem
linhas de endereço. O defeito que estes testes travam: o frete era procurado
no texto inteiro, e o "Frete grátis" vinha dos anúncios relacionados — todas
as ofertas saíam "frete não informado" e com vendedor vazio.
"""
import json
import re
from pathlib import Path

from precos.lojas.mercado_livre import ler_caixa, ler_jsonld

FIX = Path(__file__).parent / "fixtures" / "mercado_livre"


def ld(nome):
    return json.loads((FIX / f"{nome}-jsonld.json").read_text(encoding="utf-8"))


def txt(nome):
    return (FIX / f"{nome}-texto.txt").read_text(encoding="utf-8")


def test_mercado_livre_frete_pago_vem_do_jsonld():
    r = ler_jsonld(ld("fei27t-frete-pago"))
    assert {k: r[k] for k in ("preco", "frete", "dias")} == {"preco": 2579.25, "frete": 256.99, "dias": 12}


def test_mercado_livre_caixa_de_compra_da_cartao_vendedor_e_prazo():
    assert ler_caixa(txt("fei27t-frete-pago")) == (2715.0, "Mega Mamute", "Chegará quinta-feira", False)


def test_mercado_livre_frete_gratis():
    assert ler_jsonld(ld("hb150-frete-gratis"))["frete"] == 0.0
    cartao, vend, prazo, gratis = ler_caixa(txt("hb150-frete-gratis"))
    assert vend == "LOJAS UD" and prazo == "Chegará grátis sexta-feira 6 de novembro" and gratis


def test_mercado_livre_fixture_nao_leva_o_cep_do_destino():
    for nome in ("fei27t-frete-pago", "hb150-frete-gratis", "agua-mercado"):
        for bloco in ld(nome):
            destino = json.loads(bloco)["offers"]["shippingDetails"].get("shippingDestination", {})
            assert destino.get("postalCode", "00000000") == "00000000"


def test_mercado_livre_sem_jsonld_de_oferta():
    assert ler_jsonld(['{"@type": "BreadcrumbList"}', "não é json"]) is None


def test_mercado_livre_layout_de_mercado_sem_comprar_agora():
    """Item de mercado só tem "Adicionar ao carrinho"; a caixa se acha pelo link de entrega."""
    r = ler_jsonld(ld("agua-mercado"))
    assert {k: r[k] for k in ("preco", "frete", "dias")} == {"preco": 24.17, "frete": 20.99, "dias": 2}
    cartao, vend, prazo, gratis = ler_caixa(txt("agua-mercado"))
    assert (vend, prazo, gratis) == ("Premium", "Chegará amanhã sábado", False)


def test_mercado_livre_fora_de_estoque_nao_vira_oferta():
    blocos = ld("fei27t-frete-pago")
    j = json.loads(blocos[0]); j["offers"]["availability"] = "https://schema.org/OutOfStock"
    assert ler_jsonld([json.dumps(j)]) is None


# Página com variantes (colchão): o JSON-LD é um ProductGroup, um preço por tamanho.
# Até 01/11 o leitor só conhecia Product, e todo colchão dava zero ofertas, calado.
GRUPO = json.dumps({"@type": "ProductGroup", "name": "Colchão Guldi Duplo Plus D28", "hasVariant": [
    {"@type": "Product", "name": "Colchão Casal Guldi Duplo Plus D28 (16x138x188)",
     "offers": {"price": 852.03, "availability": "https://schema.org/InStock",
                "url": "https://www.mercadolivre.com.br/colchao-casal-guldi/p/MLB36229349"}},
    {"@type": "Product", "name": "Colchão Queen Guldi Duplo Plus D28 (16x158x198)",
     "offers": {"price": 1219.88, "availability": "https://schema.org/InStock",
                "url": "https://www.mercadolivre.com.br/colchao-queen-guldi/p/MLB36768447"}},
    {"@type": "Product", "name": "Colchão Solteirão King Guldi Duplo Plus D28",
     "offers": {"price": 779.95, "availability": "https://schema.org/InStock",
                "url": "https://www.mercadolivre.com.br/colchao-solteirao-guldi/p/MLB49485085"}},
]})
SEM_QUEEN_NEM_SOLTEIRO = lambda nome: not re.search(r"queen|king|solteir", nome, re.I)


def test_product_group_vale_a_variante_da_pagina():
    r = ler_jsonld([GRUPO], "https://www.mercadolivre.com.br/colchao-queen-guldi/p/MLB36768447#x", SEM_QUEEN_NEM_SOLTEIRO)
    assert r["preco"] == 1219.88 and "Queen" in r["nome"]          # o id da página manda, mesmo sendo queen


def test_product_group_sem_id_vale_a_mais_barata_que_passa_nas_regras():
    r = ler_jsonld([GRUPO], "https://lista.mercadolivre.com.br/x", SEM_QUEEN_NEM_SOLTEIRO)
    assert r["preco"] == 852.03 and r["url"].endswith("/p/MLB36229349")   # o solteirão é mais barato, mas sai


def test_product_group_sem_variante_aceita_fica_de_fora():
    assert ler_jsonld([GRUPO], "", lambda nome: False) is None
    assert ler_jsonld([GRUPO]) is None                                     # sem regra nem id: não chuta tamanho
