"""Vigia: atende o botão "Atualizar agora" e os pedidos de monitor sem esperar o próximo logon.

Depois da rodada do logon, o lançador fica rodando isto em segundo plano. A cada
`vigia_minutos` (config.toml, padrão 5) uma única consulta ao GitHub lista as
issues abertas do repositório:

  - "atualizar" (o botão da página abre uma issue com esse rótulo): roda todos
    os monitores agora, publica, comenta a hora e fecha a issue;
  - "novo-monitor": roda `monitor.py --pedidos`, que cria o monitor e já o pesquisa;
  - "gerenciar-monitor" (pausar, retomar, excluir): o mesmo `--pedidos`, que muda o
    arquivo do monitor e republica a página.

Só issues abertas pelo dono do repositório disparam alguma coisa; as de outras
contas ficam como estão e só viram uma linha no log. Nada do texto da issue é
lido aqui — o rótulo e o autor bastam.

Custo: entre uma consulta e outra o processo dorme (não impede o notebook de
suspender). Sem rede, a consulta falha, vai uma linha ao log e tenta de novo
na volta seguinte. Um segundo vigia não sobe: o primeiro segura uma trava.
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
from datetime import datetime

from .base import DADOS, RAIZ, SEM_JANELA

ATUALIZAR = "atualizar"
NOVO_MONITOR = "novo-monitor"
GERENCIAR = "gerenciar-monitor"
TRAVA = DADOS / "vigia.lock"


def gh(*args) -> str:
    r = subprocess.run(["gh", *args], cwd=RAIZ, capture_output=True, text=True, encoding="utf-8",
                       creationflags=SEM_JANELA, timeout=60)
    if r.returncode:
        raise RuntimeError(f"gh {args[0]}: {r.stderr.strip()[:200]}")
    return r.stdout


def pendencias(issues: list[dict], dono: str) -> tuple[list[int], bool, list[str]]:
    """(issues "atualizar" do dono, há pedido de monitor do dono, avisos sobre as de terceiros)."""
    atualizar, pedido, avisos = [], False, []
    for i in issues:
        rotulos = {r["name"] for r in i.get("labels", [])}
        if not rotulos & {ATUALIZAR, NOVO_MONITOR, GERENCIAR}:
            continue
        if i["author"]["login"] != dono:
            avisos.append(f"issue #{i['number']} de @{i['author']['login']} ignorada (só o dono dispara)")
            continue
        if ATUALIZAR in rotulos:
            atualizar.append(i["number"])
        if rotulos & {NOVO_MONITOR, GERENCIAR}:
            pedido = True
    return atualizar, pedido, avisos


def rodar_monitor(*args) -> int:
    """Em outro processo: um erro numa rodada não derruba o vigia."""
    return subprocess.call([sys.executable, str(RAIZ / "monitor.py"), *args, "--sem-abrir"], cwd=RAIZ,
                           creationflags=SEM_JANELA)


def travar():
    """Segura dados/vigia.lock enquanto o processo vive; None se outro vigia já segura."""
    import msvcrt
    TRAVA.parent.mkdir(parents=True, exist_ok=True)
    f = open(TRAVA, "a+")
    try:
        msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
    except OSError:
        f.close()
        return None
    return f


def uma_volta(repo: str, log, ja_avisado: set[str]) -> None:
    dono = repo.split("/")[0]
    issues = json.loads(gh("issue", "list", "-R", repo, "--state", "open", "--limit", "50",
                           "--json", "number,labels,author"))
    atualizar, pedido, avisos = pendencias(issues, dono)
    for a in avisos:
        if a not in ja_avisado:  # uma vez por issue, não a cada volta
            log("Vigia: " + a)
            ja_avisado.add(a)
    if pedido:
        log("Vigia: pedido de monitor aberto; atendendo agora.")
        rodar_monitor("--pedidos")
    if atualizar:
        log(f"Vigia: atualização pedida (#{', #'.join(map(str, atualizar))}); rodando todos os monitores.")
        codigo = rodar_monitor("--todos")
        texto = (f"Atualizado às {datetime.now():%H:%M} de {datetime.now():%d/%m}; a página já tem os preços novos."
                 if codigo == 0 else "A rodada terminou com erro; veja o monitor.log no notebook.")
        for n in atualizar:
            gh("issue", "comment", str(n), "-R", repo, "--body", texto)
            gh("issue", "close", str(n), "-R", repo)


def vigiar(repo: str, minutos: float, log) -> None:
    trava = travar()
    if trava is None:
        log("Vigia: já há outro rodando; este sai.")
        return
    log(f"Vigia: olhando {repo} a cada {minutos:g} min.")
    ja_avisado: set[str] = set()
    falhando = False
    while True:
        try:
            uma_volta(repo, log, ja_avisado)
            if falhando:
                log("Vigia: GitHub respondendo de novo.")
            falhando = False
        except Exception as exc:  # sem rede, gh fora do ar: tenta de novo na próxima volta
            if not falhando:
                log(f"Vigia: consulta falhou ({exc!r}); sigo tentando.")
            falhando = True
        time.sleep(minutos * 60)
