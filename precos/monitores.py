"""Os monitores, montados a partir de quatro arquivos com donos diferentes:

  config.toml          opções gerais
  lojas.toml           o registro único de lojas — todo monitor pesquisa todas
  monitores/<id>.toml  o que cada monitor procura (um arquivo por monitor)
  local.toml           o que é pessoal (o CEP); fica fora do git

O cfg que os coletores recebem junta os quatro, então eles continuam lendo
cfg["cep"], cfg["lojas"], cfg["lojas_api"] e cfg["lojas_navegador"]. O freezer
guarda o que gera em dados/, onde sempre esteve; os outros em dados/<id>/.
"""
from __future__ import annotations

import tomllib
from pathlib import Path

from .base import DADOS, ESTADO, HISTORICO, RAIZ, RELATORIO

CONFIG_GERAL = RAIZ / "config.toml"
LOJAS = RAIZ / "lojas.toml"
LOCAL = RAIZ / "local.toml"
PASTA_MONITORES = RAIZ / "monitores"


class ConfiguracaoInvalida(Exception):
    pass


def ler_toml(caminho: Path, obrigatorio: bool = True) -> dict:
    try:
        with caminho.open("rb") as f:
            return tomllib.load(f)
    except FileNotFoundError:
        if obrigatorio:
            raise ConfiguracaoInvalida(f"falta {caminho.name}")
        return {}
    except tomllib.TOMLDecodeError as e:
        raise ConfiguracaoInvalida(f"{caminho.name}: {e}")


def usar_token_do_monitor(local: dict) -> bool:
    """Se local.toml tem [github] token, este processo e os git/gh que ele chamar usam só ele.

    É um token de escopo fino, só do monitor-precos (issues e conteúdo). Sem ele,
    valem o login do gh e o Git Credential Manager da máquina, que alcançam todos os
    repositórios. Nada é gravado na configuração do git: são variáveis de ambiente
    deste processo — GH_TOKEN para o gh, e para o git o token no cabeçalho de cada
    requisição ao github.com (como faz o actions/checkout).

    O Git Credential Manager com o login amplo vem da configuração de SISTEMA do
    git, e o git recorre a ele quando uma requisição falha. Zerar o helper por
    variável não serve no Windows (variável vazia não existe ali, medido em 31/10).
    Então o processo ignora a configuração de sistema (GIT_CONFIG_NOSYSTEM) e põe
    de volta, lida na hora, tudo o que ela tem menos as linhas credential.* —
    core.autocrlf inclusive, que é de onde vem o CRLF desta máquina.
    """
    import base64
    import os
    import subprocess
    token = (local.get("github") or {}).get("token", "").strip()
    if not token:
        return False
    from .base import SEM_JANELA
    r = subprocess.run(["git", "config", "--system", "--list"], capture_output=True, text=True,
                       encoding="utf-8", creationflags=SEM_JANELA)
    sistema = [l.split("=", 1) for l in r.stdout.splitlines() if "=" in l]
    pares = [(k, v) for k, v in sistema if not k.lower().startswith("credential.") and v]
    basico = base64.b64encode(f"x-access-token:{token}".encode()).decode()
    pares.append(("http.https://github.com/.extraheader", f"AUTHORIZATION: basic {basico}"))
    os.environ["GH_TOKEN"] = token
    os.environ["GIT_CONFIG_NOSYSTEM"] = "1"
    os.environ["GCM_INTERACTIVE"] = "never"
    os.environ["GIT_CONFIG_COUNT"] = str(len(pares))
    for i, (k, v) in enumerate(pares):
        os.environ[f"GIT_CONFIG_KEY_{i}"] = k
        os.environ[f"GIT_CONFIG_VALUE_{i}"] = v
    return True


def registro_de_lojas(lojas: dict) -> dict:
    return {"lojas": lojas.get("vtex", []), "lojas_api": lojas.get("api", []),
            "lojas_navegador": lojas.get("navegador", [])}


def montar(id_: str, proprio: dict, geral: dict, lojas: dict, local: dict) -> dict:
    """O cfg de um monitor. O próprio monitor manda em tudo, menos nas lojas e no CEP."""
    cfg = geral | proprio | registro_de_lojas(lojas) | {"cep": local.get("cep", "")}
    cfg.setdefault("nome", id_)
    return cfg


def carregar(precisa_cep: bool = True) -> list[dict]:
    geral = ler_toml(CONFIG_GERAL)
    lojas = ler_toml(LOJAS)
    local = ler_toml(LOCAL, obrigatorio=False)
    if precisa_cep and not local.get("cep"):
        raise ConfiguracaoInvalida("falta o CEP: copie local.exemplo.toml para local.toml e preencha")
    monitores = []
    for arq in sorted(PASTA_MONITORES.glob("*.toml"), key=lambda a: (a.stem != "freezer", a.stem)):
        proprio = ler_toml(arq)
        if proprio.get("desligado"):
            continue
        id_ = arq.stem
        pasta = DADOS if id_ == "freezer" else DADOS / id_
        monitores.append({
            "id": id_, "cfg": montar(id_, proprio, geral, lojas, local), "arquivo": arq,
            "historico": HISTORICO if id_ == "freezer" else pasta / "historico.csv",
            "relatorio": RELATORIO if id_ == "freezer" else pasta / "relatorio.html",
            "estado": ESTADO if id_ == "freezer" else pasta / "estado.json",
        })
    return monitores


def validar_monitor(m: dict) -> None:
    """O mesmo crivo para monitor escrito à mão (teste do Actions) e criado pelo formulário."""
    import re
    if m.get("modo") not in ("acompanhado", "descoberta"):
        raise ConfiguracaoInvalida("modo precisa ser acompanhado ou descoberta")
    if "lojas" in m or "lojas_navegador" in m or "lojas_api" in m:
        raise ConfiguracaoInvalida("monitor não escolhe lojas: todas valem para todos")
    try:
        if m["modo"] == "descoberta":
            if not m.get("termos") or not m.get("titulo"):
                raise ConfiguracaoInvalida("descoberta precisa de titulo e termos")
            regras = m.get("regras", {})
            for r in regras.get("incluir", []) + regras.get("excluir", []):
                re.compile(r)
        else:
            for p in m["produtos"]:
                if not p.get("modelo") or not p.get("busca"):
                    raise ConfiguracaoInvalida("cada produto precisa de modelo e busca")
                re.compile(p["padrao"])
    except re.error as e:
        raise ConfiguracaoInvalida(f"regra inválida: {e}")
