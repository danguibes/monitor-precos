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


def test_recuperacao_so_quando_o_dia_passou_e_sem_insistir():
    from datetime import datetime, timedelta
    from precos.vigia import atrasada
    agora = datetime(2026, 11, 2, 19, 0)
    assert atrasada(agora, agora - timedelta(hours=25), None, 24)          # hibernou o dia todo: roda
    assert not atrasada(agora, agora - timedelta(hours=10), None, 24)      # já rodou hoje
    assert atrasada(agora, None, None, 24)                                 # nunca rodou
    assert not atrasada(agora, agora - timedelta(days=3), agora - timedelta(minutes=30), 24)  # tentou há pouco
    assert atrasada(agora, agora - timedelta(days=3), agora - timedelta(hours=3), 24)
    assert not atrasada(agora, None, None, 0)                              # desligada no config.toml


def test_tarefa_acorda_o_notebook_so_na_tomada_e_roda_o_logon():
    import xml.etree.ElementTree as ET
    xml = instalar.tarefa_xml("06:00")
    ns = {"t": "http://schemas.microsoft.com/windows/2004/02/mit/task"}
    raiz = ET.fromstring(xml.split("\n", 1)[1])                            # sem a declaração UTF-16
    s = lambda c: raiz.find(c, ns).text
    assert s("t:Settings/t:WakeToRun") == "true" and s("t:Settings/t:DisallowStartIfOnBatteries") == "true"
    assert s("t:Principals/t:Principal/t:LogonType") == "InteractiveToken"     # sessão do usuário, sem senha
    assert s("t:Actions/t:Exec/t:Arguments") == "monitor.py --logon --sem-abrir"
    assert s("t:Actions/t:Exec/t:Command").lower().endswith("pythonw.exe")    # sem janela de console
    assert s("t:Triggers/t:CalendarTrigger/t:StartBoundary").endswith("T06:00:00")


def test_trava_da_rodada_barra_a_segunda(tmp_path, monkeypatch):
    import monitor
    monkeypatch.setattr(monitor, "TRAVA_RODADA", tmp_path / "rodada.lock")
    primeira = monitor.travar_rodada()
    assert primeira is not None and monitor.travar_rodada() is None       # 01/11: duas no mesmo perfil caíram
    primeira.close()
    assert monitor.travar_rodada() is not None
