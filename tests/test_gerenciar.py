"""Pausar, retomar e excluir pela página: o .toml muda só no que precisa, e só o dono dispara."""
import tomllib
import urllib.parse

import pytest

from precos import pedidos
from precos.pedidos import PedidoInvalido, acao_do_pedido, marcar_pausa
from precos.publicar import gerar_indice, link_gerenciar
from precos.vigia import pendencias

AGUA = '''nome = "Água com gás"
modo = "descoberta"
termos = ["água com gás"]

[regras]
incluir = ["g[aá]s"]
montar_pack = 6
'''


def test_pausar_e_retomar_mexem_so_no_topo():
    pausado = marcar_pausa(AGUA, True)
    cfg = tomllib.loads(pausado)
    assert cfg["pausado"] is True and cfg["regras"]["montar_pack"] == 6   # caiu antes da tabela, não dentro
    assert marcar_pausa(pausado, True).count("pausado =") == 1              # pausar duas vezes não duplica
    retomado = tomllib.loads(marcar_pausa(pausado, False))
    assert "pausado" not in retomado and retomado["regras"] == tomllib.loads(AGUA)["regras"]


def test_acao_vem_do_campo_ou_do_titulo():
    assert acao_do_pedido({"acao": "Excluir"}, "Monitor: ") == "excluir"
    assert acao_do_pedido({}, "Pausar: Água com gás") == "pausar"
    with pytest.raises(PedidoInvalido):
        acao_do_pedido({}, "Monitor: Água")


def test_gerenciar_recusa_monitor_inexistente_ou_caminho_estranho(tmp_path, monkeypatch):
    monkeypatch.setattr(pedidos, "PASTA_MONITORES", tmp_path)
    for alvo in ("nao-existe", "../config"):
        corpo = f"### Ação\n\nExcluir\n\n### Monitor\n\n{alvo}\n"
        with pytest.raises(PedidoInvalido):
            pedidos.gerenciar({"title": "Excluir: x", "body": corpo})


def test_gerenciar_pausa_no_arquivo(tmp_path, monkeypatch):
    monkeypatch.setattr(pedidos, "PASTA_MONITORES", tmp_path)
    monkeypatch.setattr(pedidos, "RAIZ", tmp_path.parent)
    (tmp_path / "agua.toml").write_text(AGUA, encoding="utf-8")
    rel, frase = pedidos.gerenciar({"title": "Pausar: Água", "body": "### Ação\n\nPausar\n\n### Monitor\n\nagua\n"})
    assert rel.endswith("agua.toml") and frase.startswith("pausado")
    assert tomllib.loads((tmp_path / "agua.toml").read_text(encoding="utf-8"))["pausado"] is True
    pedidos.gerenciar({"title": "x", "body": "### Ação\n\nExcluir\n\n### Monitor\n\nagua\n"})
    assert not (tmp_path / "agua.toml").exists()


def test_vigia_atende_gerenciar_so_do_dono():
    issue = lambda autor: {"number": 9, "author": {"login": autor}, "labels": [{"name": "gerenciar-monitor"}]}
    assert pendencias([issue("dono")], "dono")[1] is True
    assert pendencias([issue("outra")], "dono")[1] is False


def test_card_pausado_mostra_retomar_e_os_links_vem_preenchidos(tmp_path):
    q = urllib.parse.parse_qs(urllib.parse.urlparse(link_gerenciar("https://github.com/d/r", "agua", "Água", "Pausar")).query)
    assert q["acao"] == ["Pausar"] and q["monitor"] == ["agua"] and q["template"] == ["gerenciar-monitor.yml"]
    itens = [{"id": "agua", "nome": "Água", "melhor": None, "ultima": None, "cfg": {"pausado": True}},
             {"id": "papel", "nome": "Papel", "melhor": None, "ultima": None, "cfg": {}}]
    gerar_indice(itens, tmp_path / "index.html", "https://github.com/d/r")
    html = (tmp_path / "index.html").read_text(encoding="utf-8")
    assert html.count(">retomar<") == 1 and html.count(">pausar<") == 1 and html.count(">excluir<") == 2
    assert 'class="pausado"' in html


def test_sigla_curta_vira_palavra_inteira():
    import re
    from precos.pedidos import palavra_para_regex
    bf = re.compile(palavra_para_regex("bf"), re.I)
    assert bf.search("Colchão BF Colchões Casal") and bf.search("Colchão Casal - BF")
    assert not bf.search("Colchão Bfresh Casal") and not bf.search("Colchão Casal ABF")
    assert re.search(palavra_para_regex("guldi"), "Colchão Guldi Casal", re.I)   # nome comum segue igual


def test_comeca_com_so_vale_no_inicio():
    import re
    from precos.pedidos import palavra_para_regex
    topper = re.compile(palavra_para_regex("começa com pillow top"), re.I)
    assert topper.search("Pillow Top Casal Guldi Dream Espuma D50 (5x138x188)")
    assert not topper.search("Colchão Casal Molas Ensacadas Premium Pillow Top Sleep 138x188cm BF Colchões")
    assert re.search(palavra_para_regex("protetor ou começa com pillow top"), "Pillow Top Casal", re.I)


def test_pedido_mexido_ha_pouco_espera():
    """Em 31/10 o vigia leu o pedido 2 s antes de a pessoa editá-lo; agora espera 3 min parado."""
    from datetime import datetime, timezone
    from precos.pedidos import recente
    agora = datetime(2026, 11, 1, 0, 58, 3, tzinfo=timezone.utc)
    assert recente({"updatedAt": "2026-11-01T00:57:00Z"}, agora) is True      # mexido 1 min antes
    assert recente({"updatedAt": "2026-11-01T00:54:00Z"}, agora) is False     # parado há 4 min
    assert recente({}, agora) is False


def test_numero_nao_pode_estar_dentro_de_outro_numero():
    """Em 01/11 "512" virou palavra inteira e reprovou todo "Xiaomi 17T 512GB": zero ofertas."""
    import re
    from precos.pedidos import palavra_para_regex
    n = re.compile(palavra_para_regex("512"), re.I)
    assert n.search("Xiaomi 17T 512GB 12GB RAM") and n.search("Xiaomi 17T 512 GB")
    assert not n.search("Xiaomi 17T 1512 mAh") and not n.search("Xiaomi 17T 5120")
    assert not re.search(palavra_para_regex("256"), "Xiaomi 17T 512GB", re.I)


def test_indice_agrupa_por_pasta_com_as_lojas_de_cada_uma(tmp_path):
    from precos.publicar import lojas_varridas
    cfg = {"lojas": [{"nome": "Mambo", "host": "x"}, {"nome": "Atacadão", "host": "y"}],
           "lojas_api": ["Pão de Açúcar"], "lojas_navegador": ["Amazon", "Assaí", "Mercado Livre"]}
    assert lojas_varridas(cfg) == ["Amazon", "Assaí (pelo Rappi)", "Atacadão", "Mambo", "Mercado Livre", "Pão de Açúcar"]
    merc = dict(cfg, pasta_nome="Mercado", pasta_ordem=2)
    elet = {"lojas": [], "lojas_api": [], "lojas_navegador": ["Magalu"], "pasta_nome": "Eletrônicos", "pasta_ordem": 0}
    itens = [{"id": i, "nome": i, "melhor": None, "ultima": None, "cfg": c}
             for i, c in (("agua", merc), ("freezer", elet), ("solto", {}))]
    gerar_indice(itens, tmp_path / "index.html", None)
    html = (tmp_path / "index.html").read_text(encoding="utf-8")
    assert html.index(">Eletrônicos ") < html.index(">Mercado ") < html.index(">Outros ")   # ordem do lojas.toml
    assert "Lojas varridas (1): Magalu" in html and "Lojas varridas (6): Amazon · Assaí (pelo Rappi)" in html
    assert html.count('<details class="pasta" data-pasta=') == 3 and html.count("<summary>") == 3   # nascem fechadas



def test_card_destaca_o_preco_por_unidade_e_o_produto_vira_complemento(tmp_path):
    from precos.base import oferta
    cfg = {"modo": "descoberta", "regras": {"volume_ml": [950, 1050]}, "pasta_nome": "Mercado", "lojas": []}
    leite = oferta("Assaí", "x", "Leite Integral Piracanjuba 1L Caixa com 12", "", 60.0, 56.28, 0.0, "", "", "")
    freezer = oferta("Magalu", "x", "Freezer Vertical 197L", "", 3000.0, 2799.0, 0.0, "", "", "")
    itens = [{"id": "leite", "nome": "Leite", "melhor": leite, "ultima": None, "cfg": cfg},
             {"id": "freezer", "nome": "Freezer", "melhor": freezer, "ultima": None, "cfg": {"pasta_nome": "Outros"}}]
    gerar_indice(itens, tmp_path / "index.html", None)
    html = (tmp_path / "index.html").read_text(encoding="utf-8")
    assert '<div class="total">R$ 4,69<span class="un">/L</span></div>' in html          # 56,28 / 12 L
    assert "R$ 56,28 entregue · Leite Integral Piracanjuba" in html
    assert '<div class="total">R$ 2.799,00</div>' in html                                # sem unidade: o total
