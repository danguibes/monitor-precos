"""A configuração do repositório: lojas, monitores e o que não pode ir para o git.

Vale também como trava para quem edita os .toml pelo site do GitHub: se um
arquivo quebrar, o Actions acusa antes de o monitor rodar.
"""
import re
import tomllib
from pathlib import Path

import pytest

from precos import coleta, monitores

RAIZ = Path(__file__).parent.parent
ARQUIVOS_MONITOR = sorted((RAIZ / "monitores").glob("*.toml"))


def test_registro_de_lojas_tem_os_tres_grupos():
    lojas = tomllib.loads((RAIZ / "lojas.toml").read_text(encoding="utf-8"))
    reg = monitores.registro_de_lojas(lojas)
    assert reg["lojas"] and reg["lojas_api"] and reg["lojas_navegador"]
    # chave solta depois de [[vtex]] cairia dentro da última loja VTEX
    assert all({"nome", "host"} <= set(l) <= {"nome", "host", "taxa_servico"} for l in reg["lojas"])


def test_toda_loja_do_registro_tem_coletor():
    lojas = monitores.registro_de_lojas(tomllib.loads((RAIZ / "lojas.toml").read_text(encoding="utf-8")))
    assert set(lojas["lojas_api"]) <= set(coleta.COLETORES_API)
    assert set(lojas["lojas_navegador"]) <= set(coleta.COLETORES)


@pytest.mark.parametrize("arq", ARQUIVOS_MONITOR, ids=lambda a: a.stem)
def test_cada_monitor_e_valido(arq):
    monitores.validar_monitor(tomllib.loads(arq.read_text(encoding="utf-8")))


def test_todo_monitor_recebe_todas_as_lojas():
    geral = {"intervalo_minimo_horas": 6}
    lojas = {"vtex": [{"nome": "A", "host": "a"}], "api": ["B"], "navegador": ["C"]}
    proprio = {"modo": "descoberta", "lojas_navegador": ["só esta"]}  # tentativa de escolher
    cfg = monitores.montar("x", proprio, geral, lojas, {"cep": "1"})
    assert cfg["lojas_navegador"] == ["C"] and cfg["lojas_api"] == ["B"] and cfg["cep"] == "1"


def test_nada_pessoal_no_que_vai_para_o_git():
    """O CEP de casa mora em local.toml; nenhum arquivo rastreável pode tê-lo."""
    local = RAIZ / "local.toml"
    if not local.exists():
        pytest.skip("sem local.toml (no Actions não há CEP para procurar)")
    cep = tomllib.loads(local.read_text(encoding="utf-8")).get("cep", "")
    digitos = re.sub(r"\D", "", cep)
    padrao = re.compile(re.escape(cep) + "|" + digitos)
    ignorados = ("dados", ".git", "__pycache__", ".pytest_cache")
    achados = [str(a.relative_to(RAIZ)) for a in RAIZ.rglob("*")
               if a.is_file() and a.name != "local.toml" and not set(a.relative_to(RAIZ).parts) & set(ignorados)
               and padrao.search(a.read_text(encoding="utf-8", errors="ignore"))]
    assert not achados, f"CEP de casa em: {achados}"


def test_local_toml_fica_fora_do_git():
    """O CEP mora em local.toml; se a linha sair do .gitignore, o CEP vai junto para o repositório público."""
    linhas = (RAIZ / ".gitignore").read_text(encoding="utf-8").splitlines()
    assert "local.toml" in linhas and "dados/" in linhas


def test_pasta_escolhe_as_lojas_e_sem_pasta_valem_todas():
    lojas = {"vtex": [{"nome": "A", "host": "a"}, {"nome": "Z", "host": "z"}], "api": ["B"], "navegador": ["C", "D"],
             "pastas": {"eletro": {"nome": "Eletro", "lojas": ["Z", "D"]}, "merc": {"nome": "Merc", "lojas": ["A", "B"]}}}
    cfg = monitores.montar("x", {"pasta": "merc"}, {}, lojas, {})
    assert [l["nome"] for l in cfg["lojas"]] == ["A"] and cfg["lojas_api"] == ["B"] and cfg["lojas_navegador"] == []
    assert cfg["pasta_nome"] == "Merc" and cfg["pasta_ordem"] == 1
    for proprio in ({}, {"pasta": "inexistente"}):          # esquecer a pasta nunca deixa de procurar
        cfg = monitores.montar("x", proprio, {}, lojas, {})
        assert len(cfg["lojas"]) == 2 and cfg["lojas_navegador"] == ["C", "D"] and cfg["pasta_nome"] == "Outros"


def test_toda_pasta_e_todo_monitor_batem_com_o_registro():
    lojas = tomllib.loads((RAIZ / "lojas.toml").read_text(encoding="utf-8"))
    reg = monitores.registro_de_lojas(lojas)
    nomes = {l["nome"] for l in reg["lojas"]} | set(reg["lojas_api"]) | set(reg["lojas_navegador"])
    for id_, p in lojas["pastas"].items():
        assert set(p["lojas"]) <= nomes, f"pasta {id_} com loja fora do registro: {set(p['lojas']) - nomes}"
    for arq in ARQUIVOS_MONITOR:
        pasta = tomllib.loads(arq.read_text(encoding="utf-8")).get("pasta")
        assert pasta in lojas["pastas"], f"{arq.stem}: pasta {pasta!r} não existe em lojas.toml"
