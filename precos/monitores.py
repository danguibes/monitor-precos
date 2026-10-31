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
