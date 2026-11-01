"""O endereço local do vigia: só a página publicada dispara, e só uma rodada."""
import json
import urllib.error
import urllib.request

import pytest

from precos import vigia


@pytest.fixture
def servidor():
    pedidos = vigia.Pedidos()
    srv = vigia.servir(0, pedidos, lambda m: None)  # porta 0: o sistema escolhe uma livre
    yield srv.server_address[1], pedidos
    srv.shutdown()


def chamar(porta, caminho, origem="https://danguibes.github.io", metodo="POST"):
    req = urllib.request.Request(f"http://127.0.0.1:{porta}{caminho}", method=metodo, data=b"" if metodo == "POST" else None,
                                 headers={"Origin": origem} if origem else {})
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            return r.status, dict(r.headers), r.read()
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers), b""


def test_a_pagina_dispara_todos_e_um_monitor(servidor):
    porta, pedidos = servidor
    st, cab, corpo = chamar(porta, "/atualizar")
    assert st == 202 and json.loads(corpo)["alvo"] == "*" and cab["Access-Control-Allow-Origin"] == "https://danguibes.github.io"
    st, _, corpo = chamar(porta, "/atualizar/agua-com-gas")
    assert st == 202 and json.loads(corpo)["alvo"] == "agua-com-gas"
    assert pedidos.tirar() == {"*", "agua-com-gas"} and pedidos.evento.is_set()


def test_outra_origem_ou_sem_origem_leva_403(servidor):
    porta, pedidos = servidor
    assert chamar(porta, "/atualizar", origem="https://site-qualquer.com")[0] == 403
    assert chamar(porta, "/atualizar", origem="")[0] == 403
    assert pedidos.tirar() == set()


def test_monitor_inexistente_ou_caminho_estranho_leva_404(servidor):
    porta, pedidos = servidor
    assert chamar(porta, "/atualizar/nao-existe")[0] == 404
    assert chamar(porta, "/atualizar/../config")[0] == 404
    assert pedidos.tirar() == set()


def test_pre_voo_do_navegador_libera_a_rede_privada(servidor):
    porta, _ = servidor
    st, cab, _ = chamar(porta, "/atualizar", metodo="OPTIONS")
    assert st == 204 and cab["Access-Control-Allow-Private-Network"] == "true"


def test_volta_do_vigia_roda_o_que_foi_pedido(monkeypatch):
    rodou = []
    monkeypatch.setattr(vigia, "rodar_monitor", lambda *a: rodou.append(a) or 0)
    p = vigia.Pedidos()
    p.pedir("agua-com-gas"); p.pedir("freezer")
    vigia.atender_locais(p, lambda m: None)
    assert rodou == [("--monitor", "agua-com-gas"), ("--monitor", "freezer")]
    rodou.clear(); p.pedir("freezer"); p.pedir("*")
    vigia.atender_locais(p, lambda m: None)
    assert rodou == [("--todos",)]  # "todos" engole os pedidos de um só
