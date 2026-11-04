"""Os formatos medidos em 04/11/2026 no Mercado Livre, com títulos genéricos e números de pedido inventados."""
import json
from datetime import date
from decimal import Decimal as D

import pytest

from precos.compras_online import (deduzir_data, detalhe_da_transacao, entregue_hoje, fecha, itens_da_lista,
                                   linhas_para_envio, reais, seguras)

LINK = "https://myaccount.mercadolivre.com.br/post-purchase/my-purchases/{}/status?packId={}&orderId={}"


def lista(*compras):
    linhas = ["Histórico de compras"]
    for titulo, quando, valor in compras:
        linhas += [titulo, f"Comprado em {quando} | R$ {valor}", "Comprar novamente", "Ver detalhe"]
    return linhas


def detalhe(*miolo, pago="1x R$ 64,68", numero="1111"):
    return ["Meu endereço de casa", "Detalhes da transação", "1 de novembro |", f"#{numero}", *miolo,
            "Total pago", pago, "Meio de pagamento original"]


@pytest.mark.parametrize("texto, esperado", [
    ("1 de nov.", date(2026, 11, 1)),      # este ano
    ("5 de set.", date(2026, 9, 5)),
    ("4 de novembro", date(2026, 11, 4)),  # hoje não é futuro
    ("5 de nov.", date(2025, 11, 5)),      # amanhã: é do ano passado
    ("20 de dez.", date(2025, 12, 20)),
    ("3 de mar. de 2024", date(2024, 3, 3)),  # com ano escrito, vale o escrito
    ("29 de fev.", date(2024, 2, 29)),     # só existe em ano bissexto
    ("ontem", None),
    ("40 de nov.", None),
])
def test_ano_que_nao_poe_a_data_no_futuro(texto, esperado):
    assert deduzir_data(texto, date(2026, 11, 4)) == esperado


def test_entrega_uma_vez_por_dia():
    hoje = date(2026, 11, 4)
    assert not entregue_hoje(hoje, {})
    assert entregue_hoje(hoje, {"_ultima_entrega": "2026-11-04"})
    assert not entregue_hoje(hoje, {"_ultima_entrega": "2026-11-03"})


def test_reais():
    assert reais("1.234,56") == D("1234.56") and reais("89") == D(89)


def test_lista_casa_titulo_com_link_e_separa_transacao_de_item():
    itens = itens_da_lista(lista(("Produto A", "1 de nov.", "43,69")), [LINK.format("1111", "2222", "3333")])
    i = itens[0]
    assert (i["titulo"], i["data_texto"], i["valor_total"]) == ("Produto A", "1 de nov.", D("43.69"))
    assert (i["pedido_externo"], i["item_externo"]) == ("1111", "3333")
    assert "?" not in i["url"]


def test_lista_com_contagem_diferente_nao_chuta():
    with pytest.raises(ValueError):
        itens_da_lista(lista(("Produto A", "1 de nov.", "43,69")), [])


def test_frete_pago_com_desconto_no_produto():
    d = detalhe_da_transacao(detalhe("Produto A", "1 unidade", "R$ 45,99", "Desconto à vista", "- R$ 2,30",
                                     "Frete", "R$ 20,99"))
    assert (d["numero"], d["frete"], d["total_pago"]) == ("1111", D("20.99"), D("64.68"))
    assert d["quantidades"] == {"Produto A": 1}
    assert fecha([D("43.69")], d["frete"], d["total_pago"])  # o valor da lista, não o do detalhe


def test_frete_gratis_e_zero_nunca_o_que_se_poupou():
    d = detalhe_da_transacao(detalhe("1 unidade", "R$ 69,90", "Frete grátis", "R$ 9,40", pago="1x R$ 69,90"))
    assert d["frete"] == 0 and fecha([D("69.90")], d["frete"], d["total_pago"])


def test_frete_gratis_em_duas_linhas():
    d = detalhe_da_transacao(detalhe("R$ 21,99", "Frete", "Grátis", pago="1x R$ 21,99"))
    assert d["frete"] == 0


def test_frete_com_desconto_vale_o_ultimo():
    d = detalhe_da_transacao(detalhe("Frete com desconto", "R$ 23,69", "R$ 12,99", pago="1x R$ 400,84"))
    assert d["frete"] == D("12.99")


def test_parcelado_nao_vira_total():
    d = detalhe_da_transacao(detalhe("Frete", "R$ 1,00", pago="3x R$ 21,56"))
    assert d["total_pago"] is None
    assert not fecha([D("64.68")], d["frete"], d["total_pago"])


def test_sem_bloco_da_transacao():
    assert detalhe_da_transacao(["Minhas compras", "Total pago", "1x R$ 1,00"]) is None


def test_endereco_fora_do_bloco_nao_entra():
    assert "Meu endereço de casa" not in detalhe_da_transacao(detalhe("Frete", "R$ 1,00"))["bloco"]


def test_seguras_tira_endereco_cep_e_termo_proibido():
    linhas = ["Rua das Flores, 10", "01234-567", "Bairro Secreto", "Produto A", "1 unidade"]
    assert seguras(linhas, ["secreto"]) == ["Produto A", "1 unidade"]


def _item(transacao, ordem, valor, titulo="Produto A"):
    return {"pedido_externo": transacao, "item_externo": ordem, "titulo": titulo, "data_texto": "5 de set.",
            "valor_total": D(valor), "linha_lista": f"Comprado em 5 de set. | R$ {valor}", "url": f"/x/{transacao}/status"}


def test_varios_itens_uma_transacao_soma_com_um_frete_so():
    itens = [_item("9", "1", "89"), _item("9", "2", "89"), _item("9", "3", "78.90"), _item("9", "4", "130.95")]
    detalhes = {"9": {"frete": "12.99", "total_pago": "400.84", "quantidades": {"Produto A": 1}, "bloco": ["R$ 89"]}}
    linhas, avisos = linhas_para_envio(itens, detalhes, "danilo", [])
    assert not avisos and len(linhas) == 4
    assert {l["item_externo"] for l in linhas} == {"1", "2", "3", "4"}
    assert all(l["frete"] == D("12.99") and l["total_pago"] == D("400.84") for l in linhas)


def test_transacao_que_nao_fecha_nao_sai_e_avisa():
    detalhes = {"9": {"frete": "1.00", "total_pago": "99.00", "quantidades": {}, "bloco": []}}
    linhas, avisos = linhas_para_envio([_item("9", "1", "10")], detalhes, "danilo", [])
    assert linhas == [] and len(avisos) == 1


def test_cupom_que_a_lista_nao_desconta_sai_do_item_unico():
    bloco = ["Produto A", "2 unidades", "R$ 80", "Cupons", "- R$ 4", "Frete", "Grátis", "Total pago", "1x R$ 76"]
    detalhes = {"9": {"frete": "0", "total_pago": "76", "quantidades": {"Produto A": 2}, "bloco": bloco}}
    linhas, avisos = linhas_para_envio([_item("9", "1", "80")], detalhes, "danilo", [])
    assert not avisos and linhas[0]["valor_total"] == D(76) and linhas[0]["quantidade"] == 2


def test_cupom_em_varios_itens_nao_e_repartido():
    bloco = ["R$ 50", "R$ 50", "Cupons", "- R$ 4", "Total pago", "1x R$ 96"]
    detalhes = {"9": {"frete": "0", "total_pago": "96", "quantidades": {}, "bloco": bloco}}
    linhas, avisos = linhas_para_envio([_item("9", "1", "50"), _item("9", "2", "50")], detalhes, "danilo", [])
    assert linhas == [] and "repartir" in avisos[0]


def test_sem_detalhe_ainda_fica_para_depois_sem_aviso():
    assert linhas_para_envio([_item("9", "1", "10")], {}, "danilo", []) == ([], [])


def test_bruto_nao_leva_endereco_mesmo_vindo_de_cache_antigo():
    detalhes = {"9": {"frete": "0", "total_pago": "10", "quantidades": {}, "bloco": ["Rua das Flores, 10", "R$ 10"]}}
    linhas, _ = linhas_para_envio([_item("9", "1", "10")], detalhes, "danilo", [])
    bruto = json.loads(linhas[0]["bruto"])
    assert bruto["detalhe"] == ["R$ 10"]
