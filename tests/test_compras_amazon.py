"""O detalhe de pedido da Amazon como medido em 09/11/2026, com títulos e números inventados."""
import json
from datetime import date
from decimal import Decimal as D

from precos.compras_amazon import _para_cache, linhas_para_envio, pedido_do_detalhe
from precos.compras_online import seguras

HOJE = date(2026, 11, 9)


def detalhe(*itens, subtotal="38,00", frete="14,55", total="52,55", situacao="Entregue no dia 21 outubro"):
    linhas = ["Detalhes do pedido", "Pedido realizado 19 de outubro de 2026  Nº do pedido 111-0000000-0000000",
              "Enviar para", "Fulano de Tal", "Forma de pagamento", "Mastercardterminando em 1234",
              "Resumo do pedido", "Subtotal do(s) item(ns):", f"R$ {subtotal}", "Frete e manuseio:", f"R$ {frete}",
              "Total:", f"R$ {total}", "Total geral:", f"R$ {total}", situacao]
    for titulo, preco in itens:
        linhas += [titulo, "Vendido por: Loja X", "Condição: Novo", f"R${preco}", f"R${preco}", "Comprar novamente"]
    return linhas + ["Produto recomendado", "R$99,90", "De: R$ 120,00"]


def test_um_item_com_frete_e_data_com_ano():
    p = pedido_do_detalhe(detalhe(("Livro A", "38,00")), HOJE)
    assert (p["data"], p["subtotal"], p["frete"], p["total"]) == (date(2026, 10, 19), D(38), D("14.55"), D("52.55"))
    assert p["itens"] == [{"titulo": "Livro A", "valor": D(38)}]
    assert p["situacao"] == "Entregue no dia 21 outubro"


def test_recomendacao_nao_vira_item():
    p = pedido_do_detalhe(detalhe(("Livro A", "38,00")), HOJE)
    assert [i["titulo"] for i in p["itens"]] == ["Livro A"]


def test_recorte_nao_leva_destinatario_nem_cartao():
    bloco = _para_cache(pedido_do_detalhe(detalhe(("Livro A", "38,00")), HOJE), [])["bloco"]
    assert not any("Fulano" in l or "1234" in l or "Mastercard" in l for l in bloco)
    assert "R$ 52,55" in bloco


def test_seguras_pega_cartao_colado():
    assert seguras(["Mastercardterminando em 1234", "Visa final 9999", "R$ 10,00"], []) == ["R$ 10,00"]


def test_varios_itens_ganham_item_externo_proprio():
    p = pedido_do_detalhe(detalhe(("A", "20,00"), ("B", "18,00")), HOJE)
    cache = {"111-0000000-0000000": _para_cache(p, [])}
    linhas, avisos = linhas_para_envio(["111-0000000-0000000"], cache, "danilo", [])
    assert not avisos and [l["item_externo"] for l in linhas] == ["111-0000000-0000000#1", "111-0000000-0000000#2"]
    assert all(l["frete"] == D("14.55") and l["total_pago"] == D("52.55") for l in linhas)
    assert json.loads(linhas[0]["bruto"])["detalhe"]


def test_desconto_em_item_unico_sai_do_item():
    p = pedido_do_detalhe(detalhe(("A", "40,00"), subtotal="40,00", frete="0,00", total="36,00"), HOJE)
    linhas, avisos = linhas_para_envio(["1"], {"1": _para_cache(p, [])}, "danilo", [])
    assert not avisos and linhas[0]["valor_total"] == D(36) and linhas[0]["item_externo"] == "1"


def test_desconto_em_varios_itens_nao_sai():
    p = pedido_do_detalhe(detalhe(("A", "20,00"), ("B", "20,00"), subtotal="40,00", frete="0,00", total="36,00"), HOJE)
    linhas, avisos = linhas_para_envio(["1"], {"1": _para_cache(p, [])}, "danilo", [])
    assert linhas == [] and len(avisos) == 1


def test_pagina_sem_resumo_falha_em_vez_de_chutar():
    assert pedido_do_detalhe(["Pedido realizado 1 de novembro de 2026", "Livro A", "Vendido por: X"], HOJE) is None


def test_asin_vem_do_link_com_o_titulo_do_item():
    from precos.compras_amazon import asins_pelo_titulo
    itens = [{"titulo": "Livro A"}, {"titulo": "Produto B"}, {"titulo": "Sem link"}]
    links = [["Livro A", "/dp/8535902775/ref=x"], ["Produto B", "/gp/product/B0ABCDEF12?psc=1"],
             ["Recomendado", "/dp/B0ZZZZZZZZ"], ["Sem link", "/gp/css/order-details?orderID=1"]]
    asins_pelo_titulo(itens, links)
    assert [i["asin"] for i in itens] == ["8535902775", "B0ABCDEF12", None]


def test_asin_ambiguo_nao_chuta():
    from precos.compras_amazon import asins_pelo_titulo
    itens = [{"titulo": "Livro A"}]
    asins_pelo_titulo(itens, [["Livro A", "/dp/8535902775"], ["Livro A", "/dp/B0ABCDEF12"]])
    assert itens[0]["asin"] is None


def test_url_leva_o_asin_e_cache_antigo_e_relido():
    from precos.compras_amazon import _ja_lido
    p = pedido_do_detalhe(detalhe(("Livro A", "38,00")), HOJE)
    p["itens"][0]["asin"] = "8535902775"
    linhas, _ = linhas_para_envio(["1"], {"1": _para_cache(p, [])}, "danilo", [])
    assert linhas[0]["url"] == "/dp/8535902775"
    assert not _ja_lido({"itens": [{"titulo": "x", "valor": "1"}]})
    assert _ja_lido({"falhou": True}) and _ja_lido({"itens": [{"titulo": "x", "asin": None}]})
