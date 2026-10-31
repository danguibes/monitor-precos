"""Caminhos e utilidades comuns a todos os módulos."""
from __future__ import annotations

import json
import os
import subprocess
import re
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

# git e gh chamados de dentro do pythonw (logon, vigia) não piscam uma janela de console
SEM_JANELA = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0

RAIZ = Path(__file__).resolve().parent.parent
DADOS = RAIZ / "dados"  # tudo o que é gerado mora aqui, e a pasta inteira fica fora do git
HISTORICO = DADOS / "historico.csv"
ESTADO = DADOS / "estado.json"
RELATORIO = DADOS / "relatorio.html"
LOG = DADOS / "monitor.log"
PERFIL = DADOS / "perfil-navegador"

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/130.0 Safari/537.36")
PAUSA = 0.4  # segundos entre requisições, para não martelar as lojas

NUM = r"(\d{1,3}(?:\.\d{3})*,\d{2})"  # 2.879,10


def log(msg: str) -> None:
    linha = f"{datetime.now():%Y-%m-%d %H:%M:%S}  {msg}"
    print(linha)
    try:
        DADOS.mkdir(exist_ok=True)
        with LOG.open("a", encoding="utf-8") as f:
            f.write(linha + "\n")
    except OSError:
        pass


def carregar_json(caminho: Path, padrao):
    try:
        return json.loads(caminho.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return padrao


def salvar_json(caminho: Path, dados) -> None:
    caminho.parent.mkdir(exist_ok=True)
    caminho.write_text(json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8")


def http_json(url: str, corpo: dict | None = None, timeout: int = 25):
    """Retorna (status, json|None). Nunca levanta exceção de rede."""
    dados = json.dumps(corpo).encode() if corpo is not None else None
    req = urllib.request.Request(url, data=dados, method="POST" if corpo is not None else "GET")
    req.add_header("User-Agent", UA)
    req.add_header("Accept", "application/json")
    if corpo is not None:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, json.loads(r.read().decode("utf-8") or "null")
    except urllib.error.HTTPError as e:
        return e.code, None
    except (urllib.error.URLError, TimeoutError, ValueError, OSError) as e:
        return 0, str(e)
    finally:
        time.sleep(PAUSA)


def reais(centavos) -> float | None:
    return None if centavos is None else round(centavos / 100, 2)


def num(txt: str | None) -> float | None:
    """'2.879,10' -> 2879.1"""
    if not txt:
        return None
    try:
        return float(txt.replace(".", "").replace(",", "."))
    except ValueError:
        return None


def brl(v, casas: int = 2) -> str:
    if v in (None, ""):
        return "—"
    s = f"{float(v):,.{casas}f}"
    return "R$ " + s.replace(",", "X").replace(".", ",").replace("X", ".")


def brl_un(v) -> str:
    """Preço por unidade: abaixo de R$ 1 (lenço a R$ 0,086) duas casas apagariam a diferença."""
    return brl(v, 3 if v not in (None, "") and abs(float(v)) < 1 else 2)


def prazo_legivel(est: str | None) -> str:
    if not est:
        return ""
    m = re.fullmatch(r"(\d+)(bd|d|h)", est)
    if not m:
        return est
    n, u = int(m.group(1)), m.group(2)
    return {"bd": f"{n} dias úteis", "d": f"{n} dias", "h": f"{n} h"}[u]


def oferta(loja, modelo, produto, vendedor, preco, pix, frete, prazo, link, data, sku=""):
    """Monta a linha de oferta das lojas lidas pelo navegador."""
    pix = pix if pix and preco and pix < preco else (pix or preco)
    preco = preco or pix
    total_pix = round(pix + frete, 2) if pix is not None and frete is not None else pix
    total_cartao = round(preco + frete, 2) if preco is not None and frete is not None else preco
    return {"data": data, "loja": loja, "modelo": modelo, "produto": produto[:160],
            "sku": sku, "vendedor": vendedor or "", "preco": preco, "preco_pix": pix,
            "frete": frete, "prazo": prazo or ("frete não informado" if frete is None else ""),
            "total_pix": total_pix, "total_cartao": total_cartao, "link": link}
