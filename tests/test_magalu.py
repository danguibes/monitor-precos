"""Magalu: preço, Pix, vendedor e frete pelo texto real da página do produto (30/10/2026).

As fixtures foram gravadas sem as linhas de endereço e de nome da conta.
O defeito que estes testes travam: o frete era lido depois do PRIMEIRO
"Enviar para" — o da barra do topo — e saía o preço do produto como frete.
"""
from pathlib import Path

from precos.lojas.magalu import ler_frete, ler_magalu

FIX = Path(__file__).parent / "fixtures" / "magalu"


def carregar(nome):
    return (FIX / nome).read_text(encoding="utf-8")


def test_magalu_frete_do_bloco_do_produto_e_nao_da_barra_do_topo():
    pix, cartao, vend, frete, prazo = ler_magalu(carregar("produto-frete-calculado.txt"))
    assert (pix, cartao, vend) == (2279.05, 2399.00, "Magalu")
    assert frete == 49.90 and frete != cartao
    assert prazo == "até terça-feira, 03 de novembro"


def test_magalu_lojista_com_prazo_em_intervalo():
    pix, cartao, vend, frete, prazo = ler_magalu(carregar("produto-frete-de-lojista.txt"))
    assert vend == "Dufrio"
    assert frete == 153.89
    assert prazo == "entre 09 a 12 de novembro"


def test_magalu_perfil_logado_tem_outra_barra_no_topo():
    *_, frete, prazo = ler_magalu(carregar("produto-perfil-logado.txt"))
    assert (frete, prazo) == (49.90, "até terça-feira, 03 de novembro")


def test_magalu_frete_nao_calculado_fica_sem_frete():
    # linhas reais da página no navegador do monitor, quando o cálculo falhou
    t = ("R$ 2.279,05\n\nno Pix\nOu R$ 2.399,00 em 10x de R$ 239,90 sem juros\n\nVer opções de pagamento\n\n"
         "Enviar para [endereço]\nAlterar\n\nNão foi possível calcular o frete. Tente novamente.\n\n"
         "Adicionar à sacola\nComprar agora\n")
    assert ler_frete(t, 2399.0) == (None, "")


def test_magalu_trava_frete_do_tamanho_do_produto():
    t = "Enviar para [endereço]\nAlterar\nReceba amanhã\nR$ 1.525,26\nAdicionar à sacola\n"
    assert ler_frete(t, 1525.26) == (None, "")
