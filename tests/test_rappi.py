"""Assaí pelo Rappi: a loja do endereço, o cabeçalho de taxas e os produtos do __NEXT_DATA__.

Formatos medidos na página real em 01/11/2026 (busca "agua com gas"), com a loja
trocada por um id qualquer: o nome real dela traz o bairro.
"""
from precos.lojas import rappi

CAB_SEM_LOGIN = "Grande São Paulo\nEntrada\nAssaí Atacadista\nEntrega\nSeg, 8 AM\nTaxas\nEntrega grátis\n(novos usuários)\nPromoções\n"
CAB_LOGADO = "Assaí Atacadista\nEntrega\n35-50 min\nTaxas\nR$ 9,99\nPromoções\n"
CAB_GRATIS = "Assaí Atacadista\nEntrega\nHoje, 18h\nTaxas\nEntrega grátis\nPromoções\n"

PROD = lambda **k: {"product_id": "1", "name": "Minalba Água Mineral com Gás 1.5l", "presentation": "1 X 1 Und",
                    "price": "3.89", "in_stock": "true", "is_available": "true", "is_discontinued": "false", **k}


def test_loja_do_endereco_na_lista():
    hrefs = ["/lojas/900000001-mambo-nc", None, "/lojas/900000002-assaiatacadista-nc?x=1"]
    assert rappi.loja_assai(hrefs) == "https://www.rappi.com.br/lojas/900000002-assaiatacadista-nc"
    assert rappi.loja_assai(["/lojas/1-mambo"]) is None


def test_cabecalho_taxa_e_prazo():
    assert rappi.ler_cabecalho(CAB_SEM_LOGIN) == (None, "Seg, 8 AM")   # grátis só para cliente novo: não vale
    assert rappi.ler_cabecalho(CAB_LOGADO) == (9.99, "35-50 min")
    assert rappi.ler_cabecalho(CAB_GRATIS) == (0.0, "Hoje, 18h")
    assert rappi.ler_cabecalho("nada aqui") == (None, "")


def test_produtos_titulo_e_esgotado():
    dados = {"props": {"pageProps": {"fallback": {
        "storefront/900000002-assaiatacadista-nc/search/agua com gas": {"products": [
            PROD(),
            PROD(product_id="2", name="Crystal Água Mineral Natural com Gás", presentation="1 X 1,5 mL"),
            PROD(product_id="3", name="12x Crystal Com Gas 500 mL", presentation="1 X 500 mL"),
            PROD(product_id="4", in_stock="false"),                       # "Volta em breve"
        ]}}}}}
    ps = rappi.produtos_da_busca(dados)
    assert len(ps) == 4 and [rappi.disponivel(p) for p in ps] == [True, True, True, False]
    assert rappi.titulo(ps[1]) == "Crystal Água Mineral Natural com Gás 1,5 mL"   # o volume só estava na apresentação
    assert rappi.titulo(ps[2]) == "12x Crystal Com Gas 500 mL"                     # já está no nome: não repete
    assert rappi.titulo(ps[0]) == "Minalba Água Mineral com Gás 1.5l 1 Und"
    assert rappi.produtos_da_busca({}) == []
