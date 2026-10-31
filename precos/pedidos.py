"""Pedidos de monitor pelo formulário do GitHub (.github/ISSUE_TEMPLATE/novo-monitor.yml).

No começo da rodada, o notebook lê as issues abertas com o rótulo novo-monitor:

  - de outra conta que não a do dono: não toca nelas, e o aviso vai para a
    página publicada e para o log;
  - do dono: transforma as respostas em monitores/<id>.toml, valida como o
    Actions valida, faz commit e push só desse arquivo, comenta e fecha.
    Se algo não fizer sentido, comenta o problema e deixa a issue aberta.

Nada do texto do pedido é executado nem vira regex direto: as palavras são
escapadas e só então ganham as classes de acento.
"""
from __future__ import annotations

import json
import re
import subprocess
import tomllib
import unicodedata

from .base import RAIZ, SEM_JANELA
from .monitores import PASTA_MONITORES, ConfiguracaoInvalida, validar_monitor
from .unidades import volume_ml

ROTULO = "novo-monitor"
CAMPOS = {  # rótulo do campo no formulário -> chave
    "Nome": "nome", "Como procurar": "termos", "Precisa conter": "precisa", "Não pode conter": "exclui",
    "Tamanho de uma unidade": "tamanho", "Comparar o custo de quantas unidades": "pack",
    "Frequência": "frequencia", "Monitor a alterar": "monitor",
}
ACENTOS = {"a": "[aáàâã]", "e": "[eéèê]", "i": "[iíì]", "o": "[oóòôõ]", "u": "[uúùü]", "c": "[cç]"}


class PedidoInvalido(Exception):
    pass


# ---------------------------------------------------------------- leitura
def ler_corpo(corpo: str) -> dict:
    """{"nome": ..., "termos": ...} a partir do markdown que o Issue Form gera ("### Rótulo")."""
    respostas = {}
    for bloco in re.split(r"^###\s+", corpo or "", flags=re.M)[1:]:
        rotulo, _, valor = bloco.partition("\n")
        chave = CAMPOS.get(rotulo.strip())
        valor = valor.strip()
        if chave and valor and valor != "_No response_":
            respostas[chave] = valor
    return respostas


def linhas(valor: str | None) -> list[str]:
    return [l.strip() for l in (valor or "").splitlines() if l.strip()]


def sem_acento(t: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", t) if unicodedata.category(c) != "Mn")


def palavra_para_regex(texto: str) -> str:
    """'com gás ou gaseificada' -> regex que aceita qualquer das duas, com ou sem acento.

    O separador é " ou " ou uma barra COM espaços (" / "): barra colada é parte do
    termo, como em "c/gas" — partir ali daria a alternativa "c", que casa com quase tudo.
    Cada caractere é escapado antes de virar classe: o texto do pedido nunca é regex.
    """
    alternativas = []
    for alt in re.split(r"\s+ou\s+|\s+/\s+", texto.strip(), flags=re.I):
        alt = sem_acento(alt.strip().lower())
        if not alt:
            continue
        partes = []
        for c in alt:
            if c.isspace():
                if not partes or partes[-1] != r"\s*":
                    partes.append(r"\s*")
            else:
                partes.append(ACENTOS.get(c, re.escape(c)))
        alternativas.append("".join(partes))
    if not alternativas:
        raise PedidoInvalido(f"linha vazia em '{texto}'")
    return "|".join(alternativas)


def slug(nome: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", sem_acento(nome.lower())).strip("-")
    return s[:40].strip("-") or "monitor"


# ---------------------------------------------------------------- monitor
def montar_toml(r: dict, numero: int) -> tuple[str, str]:
    """(id, conteúdo do .toml) a partir das respostas do formulário."""
    nome = r.get("nome", "").strip()
    termos = linhas(r.get("termos"))
    if not nome or not termos:
        raise PedidoInvalido("faltou o nome ou os termos de busca")
    regras = {"incluir": [palavra_para_regex(l) for l in linhas(r.get("precisa"))],
              "excluir": [palavra_para_regex(l) for l in linhas(r.get("exclui"))]}
    if r.get("tamanho"):
        ml = volume_ml(r["tamanho"].replace(" ", ""))
        if not ml:
            raise PedidoInvalido(f"não entendi o tamanho '{r['tamanho']}' — use ml ou litros, como 500 ml ou 1,5 L")
        regras["volume_ml"] = [round(ml * 0.93), round(ml * 1.07)]
    if r.get("pack"):
        if not r["pack"].strip().isdigit() or not 1 < int(r["pack"]) <= 48:
            raise PedidoInvalido(f"a quantidade '{r['pack']}' precisa ser um número de 2 a 48")
        regras["montar_pack"] = int(r["pack"])
    horas = int(re.match(r"\d+", r.get("frequencia", "12")).group())
    id_ = r.get("monitor", "").strip() or slug(nome)

    s = lambda v: json.dumps(v, ensure_ascii=False)  # string TOML básica == string JSON
    lista = lambda vs: "[" + ", ".join(s(v) for v in vs) + "]"
    texto = [f"# Criado pelo formulário, pedido #{numero}. Para mudar, use o link \"editar\" da página:",
             "# ele reabre o formulário preenchido. Editar este arquivo à mão também funciona.", "",
             f"nome = {s(nome)}", f"titulo = {s(nome)}", 'modo = "descoberta"',
             f"intervalo_minimo_horas = {horas}", f"termos = {lista(termos)}", "", "[regras]",
             f"incluir = {lista(regras['incluir'])}", f"excluir = {lista(regras['excluir'])}"]
    if "volume_ml" in regras:
        texto.append(f"volume_ml = {regras['volume_ml']}")
    if "montar_pack" in regras:
        texto.append(f"montar_pack = {regras['montar_pack']}")
    # as respostas como vieram, para o "editar" reabrir o formulário preenchido
    texto += ["", "[pedido]", f"numero = {numero}", f"termos = {s(r.get('termos', ''))}",
              f"precisa = {s(r.get('precisa', ''))}", f"exclui = {s(r.get('exclui', ''))}",
              f"tamanho = {s(r.get('tamanho', ''))}", f"pack = {s(r.get('pack', ''))}", ""]
    conteudo = "\n".join(texto)
    try:
        validar_monitor(tomllib.loads(conteudo))
    except ConfiguracaoInvalida as e:
        raise PedidoInvalido(str(e))
    return id_, conteudo


# ---------------------------------------------------------------- GitHub
def gh(*args) -> str:
    r = subprocess.run(["gh", *args], cwd=RAIZ, capture_output=True, text=True, encoding="utf-8",
                       creationflags=SEM_JANELA)
    if r.returncode:
        raise RuntimeError(f"gh {args[0]} {args[1] if len(args) > 1 else ''}: {r.stderr.strip()[:200]}")
    return r.stdout


def git(*args) -> str:
    r = subprocess.run(["git", *args], cwd=RAIZ, capture_output=True, text=True, encoding="utf-8",
                       creationflags=SEM_JANELA)
    if r.returncode:
        raise RuntimeError(f"git {args[0]}: {r.stderr.strip()[:200]}")
    return r.stdout


def responder(repo: str, numero: int, texto: str, fechar: bool) -> None:
    gh("issue", "comment", str(numero), "-R", repo, "--body", texto)
    if fechar:
        gh("issue", "close", str(numero), "-R", repo)


def atender(repo: str, log) -> tuple[list[str], list[str]]:
    """Atende os pedidos abertos.

    Devolve (avisos, prontos): os avisos de pedidos de terceiros, para a página,
    e os ids dos monitores criados ou alterados, que rodam já nesta rodada.
    """
    dono = repo.split("/")[0]
    try:
        abertos = json.loads(gh("issue", "list", "-R", repo, "--label", ROTULO, "--state", "open",
                                "--json", "number,title,body,author", "--limit", "30"))
    except (RuntimeError, ValueError) as e:
        log(f"Pedidos: não consegui ler as issues ({e})")
        return [], []
    avisos, prontos = [], []
    for issue in abertos:
        n, autor = issue["number"], issue["author"]["login"]
        if autor != dono:
            avisos.append(f"Pedido #{n} aberto por @{autor} foi ignorado: só pedidos de @{dono} são atendidos.")
            continue
        r = ler_corpo(issue["body"])
        try:
            id_, conteudo = montar_toml(r, n)
            arq = PASTA_MONITORES / f"{id_}.toml"
            if r.get("monitor"):
                if not arq.exists():
                    raise PedidoInvalido(f"não existe monitor '{id_}' para alterar")
                if "[pedido]" not in arq.read_text(encoding="utf-8"):
                    raise PedidoInvalido(f"'{id_}' foi escrito à mão; altere pelo arquivo no GitHub")
            elif arq.exists():
                raise PedidoInvalido(f"já existe um monitor '{id_}' — para mudá-lo, use o link \"editar\" da página")
        except PedidoInvalido as e:
            responder(repo, n, f"Não deu para criar o monitor: **{e}**. Corrija o pedido (editar a issue) "
                               "e ele é lido de novo na próxima rodada.", fechar=False)
            log(f"Pedido #{n}: {e}")
            continue
        alterando = arq.exists()
        arq.write_text(conteudo, encoding="utf-8")
        rel = arq.relative_to(RAIZ).as_posix()
        try:
            git("add", "--", rel)
            git("commit", "-q", "-m", f"Monitor {id_} {'alterado' if alterando else 'criado'} pelo pedido #{n}",
                "--", rel)
            git("push", "-q")
        except RuntimeError as e:
            log(f"Pedido #{n}: o arquivo foi gerado mas não subiu ({e}); fica para a próxima rodada")
            continue
        responder(repo, n, f"Monitor **{r['nome']}** {'alterado' if alterando else 'criado'} em `{rel}`. "
                           "A primeira consulta começa agora, em todas as lojas; a página se atualiza quando ela terminar.", fechar=True)
        log(f"Pedido #{n}: monitor {id_} {'alterado' if alterando else 'criado'}")
        prontos.append(id_)
    for a in avisos:
        log("Pedidos: " + a)
    return avisos, prontos
