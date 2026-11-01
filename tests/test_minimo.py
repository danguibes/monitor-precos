"""Pedido mínimo da loja (Atacadão: R$ 250, medido em 01/11/2026) e o mínimo em unidades na tabela."""
from precos.lojas.vtex import pedido_minimo
from precos.relatorio import minimo_em_unidades


def test_minimo_vem_da_simulacao_em_centavos():
    assert pedido_minimo({"minimumOrderValue": 25000}) == 250.0
    assert pedido_minimo({"minimumOrderValue": 0}) is None and pedido_minimo({}) is None


def test_minimo_em_unidades_do_anuncio():
    fardo = {"loja": "Atacadão", "preco_pix": 17.34, "preco": 17.34}
    assert minimo_em_unidades(fardo, {"Atacadão": 250.0}) == "R$ 250,00 · 15 un."   # 14 fardos dão 242,76
    assert minimo_em_unidades(fardo, {"Mambo": 150.0}) == "—"                        # mínimo de outra loja
    assert minimo_em_unidades({"loja": "Atacadão", "preco_pix": 300.0}, {"Atacadão": 250.0}) == "R$ 250,00"
    assert minimo_em_unidades({"loja": "Atacadão", "preco_pix": 25.0}, {"Atacadão": 250.0}) == "R$ 250,00 · 10 un."
