"""Vigia: quem pode disparar uma rodada, e o lançador que o liga no logon."""
import instalar
from precos.vigia import pendencias


def issue(n, autor, *rotulos):
    return {"number": n, "author": {"login": autor}, "labels": [{"name": r} for r in rotulos]}


def test_so_o_dono_dispara():
    atualizar, pedido, avisos = pendencias([issue(1, "outra", "atualizar"), issue(2, "outra", "novo-monitor")], "dono")
    assert atualizar == [] and pedido is False and len(avisos) == 2


def test_atualizar_e_pedido_do_dono():
    atualizar, pedido, avisos = pendencias([issue(3, "dono", "atualizar"), issue(4, "dono", "novo-monitor"),
                                            issue(5, "dono", "bug")], "dono")
    assert atualizar == [3] and pedido is True and avisos == []


def test_issue_sem_rotulo_do_vigia_nao_gera_aviso():
    assert pendencias([issue(6, "outra", "bug"), issue(7, "outra")], "dono") == ([], False, [])


def test_lancador_roda_o_logon_e_depois_o_vigia():
    texto = instalar.lancador()
    compile(texto, "lancador.pyw", "exec")
    assert texto.index("'--logon'") < texto.index("'--vigiar'") and "except SystemExit" in texto
