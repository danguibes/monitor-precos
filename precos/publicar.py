"""Publica os relatórios, sem o CEP, no GitHub Pages (ramo gh-pages do repositório).

A coleta é sempre nesta máquina — os logins só existem aqui. Ao fim da rodada:

  1. gera dados/site/: index.html (os monitores e a melhor oferta de cada) e
     um <id>.html por monitor, na versão pública do relatório;
  2. varre o site atrás do CEP de local.toml e de cada termo da lista
     `nao_publicar` de local.toml — se achar qualquer um, NÃO publica;
  3. empurra o site como um único commit no ramo gh-pages (força: o histórico
     de preços mora no CSV, não no ramo da página).
"""
from __future__ import annotations

import html
import re
import shutil
import subprocess
import urllib.parse
from datetime import datetime
from pathlib import Path

from .base import DADOS, RAIZ, brl
from .relatorio import ESTILO, gerar_relatorio

SITE = DADOS / "site"


class PublicacaoBarrada(Exception):
    pass


def termos_proibidos(local: dict) -> list[str]:
    cep = local.get("cep", "")
    termos = [cep, re.sub(r"\D", "", cep)] + list(local.get("nao_publicar", []))
    return [t for t in termos if t]


def varrer(pasta: Path, proibidos: list[str]) -> list[str]:
    """[arquivo: termo] para cada termo proibido achado no site."""
    achados = []
    for arq in pasta.rglob("*"):
        if arq.is_file() and ".git" not in arq.parts:
            conteudo = arq.read_text(encoding="utf-8", errors="ignore").lower()
            achados += [f"{arq.name}: {t}" for t in proibidos if t.lower() in conteudo]
    return achados


MODELO = RAIZ / "modelos" / "monitor.toml"


def repo_web() -> str | None:
    """https://github.com/dono/repo a partir do remote, ou None fora de um clone do GitHub."""
    try:
        url = git("remote", "get-url", "origin", cwd=RAIZ)
    except RuntimeError:
        return None
    m = re.match(r"https://github\.com/([^/]+/[^/]+?)(\.git)?$", url)
    return f"https://github.com/{m.group(1)}" if m else None


def link_novo_monitor(repo: str) -> str:
    """Página "novo arquivo" do GitHub, já com o modelo comentado no editor."""
    modelo = MODELO.read_text(encoding="utf-8")
    return (f"{repo}/new/main/monitores?filename=novo-monitor.toml&value="
            + urllib.parse.quote(modelo))


def gerar_indice(itens: list[dict], destino: Path, repo: str | None = None) -> None:
    e = html.escape
    cards = []
    for it in itens:
        mel = it["melhor"]
        corpo = (f'<div class="total">{brl(mel["total_pix"])}</div>'
                 f'<div class="det">{e(mel["produto"][:90])} · {e(mel["loja"])}</div>') if mel else \
            '<div class="det">Sem oferta na última rodada.</div>'
        cards.append(f'<article class="card"><header><h2><a href="{e(it["id"])}.html">{e(it["nome"])}</a></h2></header>'
                     f'<div class="meta">última consulta {e(it["ultima"] or "—")}</div>{corpo}'
                     f'<a href="{e(it["id"])}.html">ver todas as ofertas →</a>'
                     + (f' · <a href="{e(repo)}/edit/main/monitores/{e(it["id"])}.toml" target="_blank" '
                        f'rel="noopener">editar</a>' if repo else "") + '</article>')
    novo = (f'<p><a class="botao" href="{e(link_novo_monitor(repo))}" target="_blank" rel="noopener">'
            f'+ Novo monitor</a> <span class="det">abre o GitHub com um modelo comentado; salve e a próxima '
            f'rodada do notebook já pesquisa em todas as lojas</span></p>') if repo else ""
    destino.write_text(f"""<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><meta name="robots" content="noindex">
<title>Monitor de preços</title><style>{ESTILO}
.botao{{display:inline-block;background:var(--ac);color:var(--card);padding:8px 14px;border-radius:10px;text-decoration:none;font-weight:600;margin-top:18px}}
</style></head><body><main>
<h1>Monitor de preços</h1>
<p class="sub">Melhor oferta de cada monitor, com o frete para um CEP fixo · gerado em {datetime.now():%Y-%m-%d %H:%M}</p>
<section class="grid">{"".join(cards)}</section>
{novo}
</main></body></html>""", encoding="utf-8")


def gerar_site(monitores: list[dict], pasta: Path = SITE, repo: str | None = None) -> None:
    from .base import carregar_json
    if pasta.exists():
        shutil.rmtree(pasta)
    pasta.mkdir(parents=True)
    itens = []
    for m in monitores:
        avisos = carregar_json(m["estado"], {}).get("avisos", [])
        res = gerar_relatorio(m["cfg"], avisos, pasta / f"{m['id']}.html", m["historico"], publico=True)
        melhores = [r["melhor"] for r in res if r["melhor"]]
        com_frete = [x for x in melhores if x.get("frete") is not None] or melhores
        melhor = min(com_frete, key=lambda x: x["total_pix"]) if com_frete else None
        itens.append({"id": m["id"], "nome": m["cfg"].get("nome", m["id"]), "melhor": melhor,
                      "ultima": melhor["data"] if melhor else None})
    gerar_indice(itens, pasta / "index.html", repo)


def git(*args, cwd: Path) -> str:
    r = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, encoding="utf-8")
    if r.returncode:
        raise RuntimeError(f"git {' '.join(args)}: {r.stderr.strip()[:300]}")
    return r.stdout.strip()


def enviar(pasta: Path = SITE) -> str:
    """Um commit só, em ramo órfão, empurrado à força para gh-pages."""
    url = git("remote", "get-url", "origin", cwd=RAIZ)
    git("init", "-q", "-b", "gh-pages", cwd=pasta)
    git("add", "-A", cwd=pasta)
    git("commit", "-q", "-m", f"Relatórios de {datetime.now():%Y-%m-%d %H:%M}", cwd=pasta)
    git("push", "-q", "-f", url, "gh-pages", cwd=pasta)
    return url


def publicar(monitores: list[dict], local: dict, log) -> bool:
    gerar_site(monitores, repo=repo_web())
    achados = varrer(SITE, termos_proibidos(local))
    if achados:
        log("Publicação BARRADA: dado pessoal no site gerado -> " + "; ".join(achados[:5]))
        return False
    try:
        url = enviar()
    except RuntimeError as e:
        log(f"Publicação falhou: {e}")
        return False
    log(f"Publicado em gh-pages de {url}")
    return True
