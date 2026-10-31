"""Vila das Frutas: cabeçalho de entrega e busca, pelo texto real da página (30/10/2026, conta logada).

As fixtures foram gravadas sem as linhas de endereço da conta, e o nome da loja
que atende a casa virou LOJA-NEUTRA: o leitor não usa nenhum dos dois.
"""
from pathlib import Path

from precos.lojas.vila_das_frutas import ler_busca, ler_entrega

FIX = Path(__file__).parent / "fixtures" / "vila_das_frutas"


def carregar(nome):
    return (FIX / nome).read_text(encoding="utf-8")


def test_vila_das_frutas_entrega_logada():
    e = ler_entrega(carregar("home-logada-entrega.txt"))
    assert e == {"frete": 15.0, "prazo": "Sáb 8h às 8:59", "gratis_acima": 350.0}


def test_vila_das_frutas_sem_login_ou_em_retirada_nao_da_frete():
    deslogada = "Clube Vila\nEntre | Cadastre-se\n0\nLoja de\nLOJA-NEUTRA\nRetirada\nAgende o horário de retirada\n"
    assert "pede login" in ler_entrega(deslogada)
    retirada = "Clube Vila\nD\nLoja de\nLOJA-NEUTRA\nRetirada\nPróximo: \nSáb • 8h às 8:59\n • R$ 0,00\n"
    assert "não é Entrega" in ler_entrega(retirada)


def test_vila_das_frutas_busca_le_os_sete_produtos():
    produtos = ler_busca(carregar("busca-agua-com-gas.txt"))
    assert len(produtos) == 7  # a página diz "Encontramos 7 itens"
    assert ("Agua Minalba Com Gas 1,5l", 4.99) in produtos
    assert ("Agua Mineral Crystal Com Gas 1,5l", 4.69) in produtos
    assert not any(t in ("Categorias", "Filtrar") for t, _ in produtos)


def test_vila_das_frutas_promocao_fica_com_o_preco_atual():
    # linhas reais da home de 30/10: preço antigo "R$ 8,99 un", desconto, preço atual
    t = ("Encontramos 2 itens\nOferta\nPatrocinado\n\n360°\n\nR$ 8,99 un\n\n-33%\n\nR$ 5,99\n\nun\n\n"
         "Leite Condensado Semidesnatado Moça Caixa 395g\n\nEXCLUSIVO ONLINE\nOferta\n\nR$ 5,49 un\n\n-36%\n\n"
         "R$ 3,49\n\nun\n\nCerveja Michelob Ultra Light Sem Glúten Lata 269ml\n\nCategorias\nHortifruti\n")
    assert ler_busca(t) == [("Leite Condensado Semidesnatado Moça Caixa 395g", 5.99),
                            ("Cerveja Michelob Ultra Light Sem Glúten Lata 269ml", 3.49)]
