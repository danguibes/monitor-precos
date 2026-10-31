"""Pão de Açúcar: escolha da loja pelo CEP e leitura da busca (respostas reais de 30/10/2026, para um CEP neutro)."""
import json
from pathlib import Path

from precos.lojas.pao_de_acucar import ler_busca, ler_entrega

FIX = Path(__file__).parent / "fixtures" / "pao_de_acucar"


def carregar(nome):
    return json.loads((FIX / f"{nome}.json").read_text(encoding="utf-8"))


def test_pao_de_acucar_escolhe_loja_pao_de_acucar_e_nao_minuto():
    e = ler_entrega(carregar("entrega-cep-neutro"))  # CEP 01310-100, Av. Paulista
    assert e["loja_id"] == 61 and e["loja"] == "0001 - Jardim Paulista"
    assert e["frete"] == 19.9
    assert e["prazo"].startswith("31/10/2026")


def test_pao_de_acucar_sem_loja_para_o_cep():
    assert ler_entrega({"deliveryTypes": []}) is None
    assert ler_entrega(None) is None


def test_pao_de_acucar_busca_so_em_estoque():
    produtos = ler_busca(carregar("busca-agua-com-gas"))
    nomes = [p[0] for p in produtos]
    assert ("Água Mineral com Gás CRYSTAL Garrafa 1,5 Litros - com 6 Unidades", 28.14) in [p[:2] for p in produtos]
    assert all(p[1] > 0 and p[3].startswith("https://www.paodeacucar.com/produto/") for p in produtos)
    dados = carregar("busca-agua-com-gas")
    sem_estoque = [p["name"] for p in dados["products"] if not p.get("stock")]
    assert sem_estoque and not set(sem_estoque) & set(nomes)
