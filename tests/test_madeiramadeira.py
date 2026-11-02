"""MadeiraMadeira: o card da busca, que é tudo que o monitor lê dela.

Textos medidos na loja em 01/11/2026. A página do produto não entra: o frete de
lá passa por um hCaptcha que, no navegador do monitor, virou desafio na tela.
"""
from precos.lojas.madeiramadeira import ler_card, titulo_do_card

CARD = ("20% CASHBACK\n\nColchão Espuma D33 Casal Lord Colchões 14x138x188\n\n(18)\nR$ 478,00\nR$ 399,00\n16% OFF\n"
        "à vista no Pix\nou 4x de R$ 99,75 sem juros")
CARD_CARO = ("Colchão Casal Molas Ensacadas Real Pillow Top 138x188x27cm Branco Inducol\n\n(12)\nR$ 899,00\nR$ 815,99\n"
             "à vista no Pix\nou 10x de R$ 89,90 sem juros")
CARD_GRATIS = ("Colchão Casal Pelmex Espuma D45 Active In Box 17 Cm (embalado a Vácuo)\n\nR$ 3.850,00\nà vista no Pix\n"
               "ou 10x de R$ 385,00 sem juros\nFRETE GRÁTIS\nSP")


def test_card_traz_pix_e_cartao_e_o_frete_so_quando_o_selo_diz():
    assert ler_card(CARD) == (399.0, 399.0, None)            # o "R$ 478" riscado não é preço; frete não dito
    assert ler_card(CARD_CARO) == (899.0, 815.99, None)      # 10x de 89,90 no cartão; Pix com desconto
    assert ler_card(CARD_GRATIS) == (3850.0, 3850.0, 0.0)    # selo de frete grátis para SP: o CEP é de SP
    assert ler_card("sem preço") == (None, None, None)


def test_titulo_pula_selo_e_avaliacao():
    assert titulo_do_card(CARD) == "Colchão Espuma D33 Casal Lord Colchões 14x138x188"
    assert titulo_do_card(CARD_GRATIS).startswith("Colchão Casal Pelmex")
