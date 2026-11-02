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
import os
import stat
import re
import shutil
import subprocess
import urllib.parse
from datetime import datetime
from pathlib import Path

from .base import DADOS, RAIZ, SEM_JANELA, brl
from .historico_pagina import gerar_historico
from .relatorio import ESTILO, SCRIPT_ATUALIZAR, botao_atualizar, gerar_relatorio, selo_augustinus

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


FORMULARIO = "novo-monitor.yml"  # .github/ISSUE_TEMPLATE/
AVISOS_PEDIDOS = DADOS / "pedidos.json"


def link_novo_monitor(repo: str) -> str:
    """O formulário do GitHub (Issue Form): campos em palavras, sem código."""
    return f"{repo}/issues/new?template={FORMULARIO}"


def link_atualizar(repo: str) -> str:
    """Abre a issue "Atualizar agora"; o vigia no notebook a atende e fecha."""
    return f"{repo}/issues/new?template=atualizar.yml"


def link_gerenciar(repo: str, id_: str, nome: str, acao: str) -> str:
    """Pausar, retomar ou excluir: o formulário já vem com a ação e o monitor preenchidos."""
    campos = {"template": "gerenciar-monitor.yml", "title": f"{acao}: {nome}", "acao": acao, "monitor": id_}
    return f"{repo}/issues/new?" + urllib.parse.urlencode(campos)


def link_editar(repo: str, id_: str, cfg: dict) -> str:
    """Monitor criado pelo formulário reabre o formulário preenchido; o escrito à mão abre o arquivo."""
    pedido = cfg.get("pedido")
    if not pedido:
        return f"{repo}/edit/main/monitores/{id_}.toml"
    campos = {"template": FORMULARIO, "title": f"Monitor: {cfg.get('nome', id_)} (alteração)",
              "nome": cfg.get("nome", ""), "termos": pedido.get("termos", ""), "precisa": pedido.get("precisa", ""),
              "exclui": pedido.get("exclui", ""), "tamanho": pedido.get("tamanho", ""),
              "pack": pedido.get("pack", ""), "monitor": id_}
    return f"{repo}/issues/new?" + urllib.parse.urlencode({k: v for k, v in campos.items() if v})


# como cada loja aparece na lista do topo, quando o nome sozinho engana
COMO_LOJA = {"Assaí": "Assaí (pelo Rappi)"}


def lojas_varridas(cfg: dict) -> list[str]:
    """As lojas que o monitor consulta (as da pasta dele, já filtradas em monitores.montar)."""
    nomes = [l["nome"] for l in cfg.get("lojas", [])] + list(cfg.get("lojas_api", [])) + list(cfg.get("lojas_navegador", []))
    return sorted({COMO_LOJA.get(n, n) for n in nomes}, key=lambda n: n.lower())


def gerar_indice(itens: list[dict], destino: Path, repo: str | None = None, avisos: list[str] = (),
                 porta: int = 0) -> None:
    """Os cards agrupados por pasta (Eletrônicos, Móveis, Mercado...), cada uma com as lojas que varre."""
    e = html.escape
    grupos: dict[str, list] = {}
    for it in sorted(itens, key=lambda it: (it.get("cfg") or {}).get("pasta_ordem", 99)):
        grupos.setdefault((it.get("cfg") or {}).get("pasta_nome", "Outros"), []).append(it)
    secoes = []
    for nome_pasta, membros in grupos.items():
        lojas = sorted({l for it in membros for l in lojas_varridas(it.get("cfg") or {})}, key=str.lower)
        linha = f'<p class="det lojas">Lojas varridas ({len(lojas)}): {" · ".join(e(l) for l in lojas)}</p>' if lojas else ""
        # <details> abre e recolhe sem script; o script só lembra, neste navegador, o que foi recolhido
        secoes.append(f'<details class="pasta" open data-pasta="{e(nome_pasta)}"><summary><h2 class="titulo-pasta">'
                      f'{e(nome_pasta)} <span class="det">{len(membros)} monitor(es)</span></h2></summary>{linha}'
                      f'<div class="grid">{"".join(_cards(membros, repo, e))}</div></details>')
    _escrever_indice(destino, secoes, repo, avisos, porta, e)


def _cards(itens, repo, e) -> list[str]:
    cards = []
    for it in itens:
        mel = it["melhor"]
        corpo = (f'<div class="total">{brl(mel["total_pix"])}</div>'
                 f'{selo_augustinus(mel, it.get("referencia"), it.get("cfg", {}))}'
                 f'<div class="det">{e(mel["produto"][:90])} · {e(mel["loja"])}</div>') if mel else \
            '<div class="det">Sem oferta na última rodada.</div>'
        pausado = (it.get("cfg") or {}).get("pausado")
        gerir = ""
        if repo:
            link = lambda acao: e(link_gerenciar(repo, it["id"], it["nome"], acao))
            gerir = (f'<div class="det acoes"><a href="{e(link_editar(repo, it["id"], it.get("cfg", {})))}" '
                     f'target="_blank" rel="noopener">editar</a> · '
                     f'<a href="{link("Retomar" if pausado else "Pausar")}" target="_blank" rel="noopener">'
                     f'{"retomar" if pausado else "pausar"}</a> · '
                     f'<a href="{link("Excluir")}" target="_blank" rel="noopener">excluir</a></div>')
        etiqueta = '<span class="pausado">pausado</span>' if pausado else ""
        cards.append(f'<article class="card{" card-pausado" if pausado else ""}"><header><h2>'
                     f'<a href="{e(it["id"])}.html">{e(it["nome"])}</a></h2>{etiqueta}</header>'
                     f'<div class="meta">última consulta {e(it["ultima"] or "—")}</div>{corpo}'
                     f'<a href="{e(it["id"])}.html">ver todas as ofertas →</a> · '
                     f'<a href="{e(it["id"])}-historico.html">histórico</a>{gerir}</article>')
    return cards


def _escrever_indice(destino, secoes, repo, avisos, porta, e) -> None:
    novo = (f'<p><a class="botao" href="{e(link_novo_monitor(repo))}" target="_blank" rel="noopener">'
            f'+ Novo monitor</a> <span class="det">abre um formulário no GitHub; com o notebook ligado, '
            f'em até 5 minutos ele cria o monitor e já pesquisa nas lojas da pasta</span></p>'
            f'<p>{botao_atualizar(porta, link_atualizar(repo))} <span class="det resposta">'
            f'{"no notebook, começa na hora; de outro aparelho, abre um pedido no GitHub que o notebook atende em até 5 minutos" if porta else "abre um pedido no GitHub; com o notebook ligado, em até 5 minutos ele roda todos os monitores"}'
            f'</span></p>') if repo else ""
    lista_avisos = "".join(f"<li>{e(a)}</li>" for a in avisos)
    destino.write_text(f"""<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><meta name="robots" content="noindex">
<title>Monitor de preços</title><style>{ESTILO}
.botao{{display:inline-block;background:var(--ac);color:var(--card);padding:8px 14px;border-radius:10px;text-decoration:none;font-weight:600;margin-top:18px}}
.lojas{{margin:0 0 12px}} .pasta{{margin:0 0 28px}}
.titulo-pasta{{font-size:20px;margin:8px 0 4px;display:inline}}
.pasta>summary{{cursor:pointer;list-style:none;border-bottom:1px solid var(--ln);margin-bottom:8px;padding:8px 0 4px}}
.pasta>summary::-webkit-details-marker{{display:none}}
.pasta>summary::before{{content:"▸";display:inline-block;width:1.1em;color:var(--mut);transition:transform .15s}}
.pasta[open]>summary::before{{transform:rotate(90deg)}}
.titulo-pasta .det{{font-weight:400}} .acoes{{margin-top:8px}} .card-pausado{{opacity:.6}}
.pausado{{border:1px solid var(--mut);color:var(--mut);border-radius:99px;font-size:11px;padding:1px 8px}}
.botao.secundario{{background:transparent;color:var(--ac);border:1.5px solid var(--ac);margin-top:4px}}
button.botao{{font:inherit;cursor:pointer}}
</style></head><body><main>
<h1>Monitor de preços</h1>
<p class="sub">Melhor oferta de cada monitor, com o frete para um CEP fixo · gerado em {datetime.now():%Y-%m-%d %H:%M}</p>
{"".join(secoes)}
{novo}
{f'<h3>Avisos</h3><ul class="avisos">{lista_avisos}</ul>' if lista_avisos else ''}
</main>{SCRIPT_PASTAS}{SCRIPT_ATUALIZAR if porta and repo else ''}</body></html>""", encoding="utf-8")


# Lembra as pastas recolhidas só neste navegador; sem localStorage (aba anônima), todas abrem.
SCRIPT_PASTAS = """<script>
(function(){var k="pastas-recolhidas",r=[];try{r=JSON.parse(localStorage.getItem(k)||"[]")}catch(_){}
document.querySelectorAll("details.pasta").forEach(function(d){
if(r.indexOf(d.dataset.pasta)>=0)d.open=false;
d.addEventListener("toggle",function(){var f=[];document.querySelectorAll("details.pasta:not([open])")
.forEach(function(x){f.push(x.dataset.pasta)});try{localStorage.setItem(k,JSON.stringify(f))}catch(_){}})})})();
</script>"""


def gerar_site(monitores: list[dict], pasta: Path = SITE, repo: str | None = None) -> None:
    from .base import carregar_json
    if pasta.exists():
        # o .git da publicação anterior tem arquivos somente leitura no Windows
        shutil.rmtree(pasta, onexc=lambda f, caminho, _: (os.chmod(caminho, stat.S_IWRITE), f(caminho)))
    pasta.mkdir(parents=True)
    itens = []
    porta = int(monitores[0]["cfg"].get("vigia_porta", 0)) if monitores else 0
    for m in monitores:
        estado = carregar_json(m["estado"], {})
        ref = estado.get("referencia_augustinus")
        botao = botao_atualizar(porta, link_atualizar(repo), m["id"], "↻ atualizar só este") if repo else ""
        res = gerar_relatorio(m["cfg"], estado.get("avisos", []), pasta / f"{m['id']}.html", m["historico"],
                              publico=True, link_historico=f"{m['id']}-historico.html", referencia=ref,
                              botao=botao, minimos=estado.get("pedido_minimo"))
        gerar_historico(m["cfg"], pasta / f"{m['id']}-historico.html", m["historico"],
                        volta=f"{m['id']}.html", publico=True)
        melhores = [r["melhor"] for r in res if r["melhor"]]
        com_frete = [x for x in melhores if x.get("frete") is not None] or melhores
        melhor = min(com_frete, key=lambda x: x["total_pix"]) if com_frete else None
        itens.append({"id": m["id"], "nome": m["cfg"].get("nome", m["id"]), "melhor": melhor,
                      "ultima": melhor["data"] if melhor else None, "cfg": m["cfg"], "referencia": ref})
    gerar_indice(itens, pasta / "index.html", repo, carregar_json(AVISOS_PEDIDOS, []), porta)


def git(*args, cwd: Path) -> str:
    r = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, encoding="utf-8",
                       creationflags=SEM_JANELA)
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
