"""Leitor da simulação de frete VTEX (Electrolux, Fast Shop, Consul, Brastemp, Compra Certa, Midea, Carrefour)."""
import json
from pathlib import Path

from precos.lojas.vtex import ler_simulacao

FIX = Path(__file__).parent / "fixtures" / "vtex"


def carregar(nome):
    return json.loads((FIX / f"{nome}.json").read_text(encoding="utf-8"))


def test_vtex_electrolux_pix_com_desconto_e_frete():
    dados, motivo = ler_simulacao(carregar("electrolux-fei27t-pix"))
    assert motivo is None
    assert dados == {"preco": 2799.0, "preco_pix": 2659.05, "frete": 49.9, "prazo": "4 dias úteis"}


def test_vtex_fastshop_parceiro_que_nao_entrega_no_cep():
    dados, motivo = ler_simulacao(carregar("fastshop-fei27t-parceiro"))
    assert dados is None
    assert "não pode ser entregue" in motivo


def test_vtex_fastshop_sem_estoque():
    dados, motivo = ler_simulacao(carregar("fastshop-fei27t-sem-estoque"))
    assert dados is None
    assert "não tem estoque" in motivo
