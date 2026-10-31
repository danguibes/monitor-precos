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


def test_vtex_so_available_vira_oferta():
    """Item sem estoque que ainda traz opção de entrega não pode passar (antes passava)."""
    sim = carregar("electrolux-fei27t-pix")
    sim["items"][0]["availability"] = "withoutStock"
    dados, motivo = ler_simulacao(sim)
    assert dados is None and "withoutStock" in motivo


def test_vtex_loja_do_cep_e_a_da_regiao_com_ponto_mais_perto(monkeypatch):
    """Atacadão: o site só vende pela loja do CEP. Ponto mais perto que não está na
    região (só retirada) é ignorado; vale a loja da região mais perto."""
    from precos.lojas import vtex
    pontos = {"items": [
        {"distance": 2.99, "pickupPoint": {"id": "loja718_autoservico_x"}},   # não está na região
        {"distance": 3.10, "pickupPoint": {"id": "loja698_autoservico_x"}},
        {"distance": 6.91, "pickupPoint": {"id": "loja133_autoservico_x"}},
    ]}
    monkeypatch.setattr(vtex, "http_json", lambda url, corpo=None: (200, pontos))
    regiao = {"loja133": "Loja B", "loja698": "Loja A"}
    assert vtex.loja_do_cep("x", "00000000", regiao, {}) == "loja698"
    assert vtex.loja_do_cep("x", "00000000", {"unica": "Loja U"}, {}) == "unica"  # Mambo, Oba
    assert vtex.loja_do_cep("y", "00000000", {"outra": "X"}, {}) == "outra"
    monkeypatch.setattr(vtex, "http_json", lambda url, corpo=None: (200, {"items": []}))
    assert vtex.loja_do_cep("z", "00000000", regiao, {}) is None  # sem ponto: sem oferta, com aviso
