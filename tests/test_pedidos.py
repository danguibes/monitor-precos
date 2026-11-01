"""Pedido de monitor pelo formulário: das respostas em palavras ao monitor validado."""
import re
import tomllib

import pytest

from precos.filtros import filtro_por_regras
from precos.pedidos import PedidoInvalido, ler_corpo, montar_toml, palavra_para_regex, slug

# o markdown que o Issue Form do GitHub gera ao enviar o formulário
CORPO = """### Nome

Água com gás 1,5 L (teste)

### Como procurar

agua com gas 1,5
agua gaseificada

### Precisa conter

água
com gás ou gaseificada / c/gas

### Não pode conter

sem gás
sabor

### Tamanho de uma unidade

1,5 L

### Comparar o custo de quantas unidades

6

### Frequência

24 horas

### Monitor a alterar

_No response_"""


def test_le_as_respostas_do_formulario():
    r = ler_corpo(CORPO)
    assert r["nome"] == "Água com gás 1,5 L (teste)"
    assert r["termos"].splitlines() == ["agua com gas 1,5", "agua gaseificada"]
    assert r["frequencia"] == "24 horas" and "monitor" not in r  # "_No response_" é vazio


def test_palavra_vira_regex_sem_acento_e_com_alternativas():
    rx = re.compile(palavra_para_regex("com gás / gaseificada"), re.I)
    for t in ("Água COM GAS", "com gás", "comgas", "Gaseificada"):
        assert rx.search(t), t
    assert not rx.search("sem gás")


def test_barra_colada_e_parte_do_termo():
    """'c/gas' não pode virar as alternativas 'c' e 'gas': 'c' casaria com quase tudo."""
    rx = re.compile(palavra_para_regex("com gás ou c/gas"), re.I)
    assert rx.search("Agua C/gas 1,5l") and rx.search("com gás")
    assert not rx.search("Água sem nada de especial, cristalina")


def test_texto_do_pedido_nunca_vira_regex_cru():
    # parênteses e + são caracteres, não operadores: o pedido não injeta regex
    rx = re.compile(palavra_para_regex("c++ (x)"), re.I)
    assert rx.search("C++ (X)") and not rx.search("cx")
    assert re.compile(palavra_para_regex(".*"), re.I).search("tudo") is None


def test_monta_monitor_valido_que_filtra_como_o_da_agua():
    id_, conteudo = montar_toml(ler_corpo(CORPO), 7)
    m = tomllib.loads(conteudo)
    assert id_ == "agua-com-gas-1-5-l-teste"
    assert m["intervalo_minimo_horas"] == 24 and m["regras"]["montar_pack"] == 6
    assert m["regras"]["volume_ml"] == [1395, 1605] and m["pedido"]["numero"] == 7
    f = filtro_por_regras(m["regras"])
    assert f("Água Mineral com Gás CRYSTAL Garrafa 1,5 Litros - com 6 Unidades")
    assert f("Agua Mineral C/gas Grf Pet 1,5l Minalba")
    assert not f("Água Mineral sem Gás MINALBA Garrafa 1,5 Litros - com 6 Unidades")
    assert not f("Água com Gás Sabor Limão 1,5L")


@pytest.mark.parametrize("campo, valor, trecho", [
    ("tamanho", "grande", "não entendi o tamanho"),
    ("pack", "seis", "precisa ser um número"),
    ("termos", "", "faltou o nome ou os termos"),
])
def test_pedido_que_nao_faz_sentido_vira_resposta_e_nao_monitor(campo, valor, trecho):
    r = ler_corpo(CORPO) | {campo: valor}
    with pytest.raises(PedidoInvalido, match=trecho):
        montar_toml(r, 1)


def test_slug():
    assert slug("Sofá retrátil 2,20 m!") == "sofa-retratil-2-20-m"


def test_atender_ignora_terceiros_e_cria_o_do_dono(tmp_path, monkeypatch):
    """O fluxo inteiro com o GitHub simulado: nada de rede, nada de commit de verdade."""
    import json as _json

    from precos import pedidos
    chamadas = []

    def gh_falso(*args):
        chamadas.append(("gh",) + args)
        if args[:2] == ("issue", "list"):
            return _json.dumps([
                {"number": 3, "title": "Monitor: x", "body": CORPO, "author": {"login": "estranho"}},
                {"number": 4, "title": "Monitor: água", "body": CORPO, "author": {"login": "dono"}},
            ])
        return ""

    monkeypatch.setattr(pedidos, "gh", gh_falso)
    monkeypatch.setattr(pedidos, "git", lambda *a: chamadas.append(("git",) + a) or "")
    monkeypatch.setattr(pedidos, "PASTA_MONITORES", tmp_path)
    monkeypatch.setattr(pedidos, "RAIZ", tmp_path.parent)
    logs = []
    avisos, prontos = pedidos.atender("dono/repo", logs.append)
    assert prontos == ["agua-com-gas-1-5-l-teste"]  # roda já, na mesma rodada

    assert avisos == ["Pedido #3 aberto por @estranho foi ignorado: só pedidos de @dono são atendidos."]
    assert not any(c[1:3] in (("issue", "comment"), ("issue", "close")) and c[3] == "3" for c in chamadas)
    criado = tmp_path / "agua-com-gas-1-5-l-teste.toml"
    assert criado.exists() and "pedido #4" in criado.read_text(encoding="utf-8")
    commits = [c for c in chamadas if c[:2] == ("git", "commit")]
    assert len(commits) == 1 and commits[0][-1].endswith("agua-com-gas-1-5-l-teste.toml")  # só esse arquivo
    assert ("gh", "issue", "close", "4", "-R", "dono/repo") in chamadas


def test_pasta_do_formulario_e_o_editar_que_mantem_a_atual():
    from precos.pedidos import preservar
    base = {"nome": "Detergente", "termos": "detergente", "frequencia": "12 horas"}
    _, novo = montar_toml(dict(base, pasta="Mercado"), 7)
    assert tomllib.loads(novo)["pasta"] == "mercado"
    _, eletro = montar_toml(dict(base, pasta="Eletrônicos"), 7)
    assert tomllib.loads(eletro)["pasta"] == "eletronicos"
    _, manter = montar_toml(dict(base, pasta="Manter a atual (ou Outros, se for novo)"), 7)
    assert "pasta" not in tomllib.loads(manter)
    assert tomllib.loads(preservar(manter, novo))["pasta"] == "mercado"          # editar sem escolher: fica
    assert tomllib.loads(preservar(eletro, novo))["pasta"] == "eletronicos"      # escolheu outra: muda
