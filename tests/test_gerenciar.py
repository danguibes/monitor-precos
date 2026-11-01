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
