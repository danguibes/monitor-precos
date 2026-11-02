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

Pelo próprio notebook há um caminho mais curto: o vigia atende também
http://127.0.0.1:<vigia_porta>/atualizar (todos) e /atualizar/<id> (um monitor).
O botão da página tenta esse endereço primeiro e, sem resposta (outro aparelho,
notebook dormindo), cai no formulário do GitHub. Só escuta na própria máquina, só
aceita pedido vindo da página do Pages (cabeçalho Origin) e só dispara rodada —
não devolve dado nenhum.

Rodada de recuperação: o notebook passa a noite em espera e o vigia fica
congelado junto. Ao acordar, se nenhum monitor consultou nas últimas
`recuperar_apos_horas` (config.toml, padrão 24), o vigia roda o `--logon` na hora.
A outra metade é a tarefa agendada (`py instalar.py --agendar`), que acorda o
notebook na tomada de madrugada.

Custo: entre uma consulta e outra o processo dorme (não impede o notebook de
suspender). Sem rede, a consulta falha, vai uma linha ao log e tenta de novo
na volta seguinte. Um segundo vigia não sobe: o primeiro segura uma trava.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
import threading
from datetime import datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from .base import DADOS, RAIZ, SEM_JANELA

ATUALIZAR = "atualizar"
NOVO_MONITOR = "novo-monitor"
GERENCIAR = "gerenciar-monitor"
TRAVA = DADOS / "vigia.lock"
ORIGENS = ("https://danguibes.github.io",)  # a página publicada; o resto leva 403
TODOS = "*"


class Pedidos:
    """O que o endereço local pediu e ainda não rodou. O servidor põe, a volta do vigia tira."""

    def __init__(self):
        self.trava, self.evento, self.fila, self.rodando = threading.Lock(), threading.Event(), set(), None

    def pedir(self, alvo: str) -> None:
        with self.trava:
            self.fila.add(alvo)
        self.evento.set()  # acorda o vigia agora, sem esperar os minutos da volta

    def tirar(self) -> set[str]:
        with self.trava:
            fila, self.fila = self.fila, set()
        return fila


def tratador(pedidos: Pedidos, existe):
    class Tratador(BaseHTTPRequestHandler):
        def _cors(self, origem):
            self.send_header("Access-Control-Allow-Origin", origem)
            self.send_header("Access-Control-Allow-Methods", "POST")
            self.send_header("Access-Control-Allow-Private-Network", "true")  # página https -> 127.0.0.1
            self.send_header("Vary", "Origin")

        def _origem_ok(self):
            origem = self.headers.get("Origin", "")
            if origem not in ORIGENS:
                self.send_response(403)
                self.end_headers()
                return None
            return origem

        def do_OPTIONS(self):
            origem = self._origem_ok()
            if origem:
                self.send_response(204)
                self._cors(origem)
                self.end_headers()

        def do_POST(self):
            origem = self._origem_ok()
            if not origem:
                return
            m = re.fullmatch(r"/atualizar(?:/([a-z0-9][a-z0-9-]{0,60}))?/?", self.path)
            if not m or (m.group(1) and not existe(m.group(1))):
                self.send_response(404)
                self._cors(origem)
                self.end_headers()
                return
            alvo = m.group(1) or TODOS
            ocupado = pedidos.rodando
            pedidos.pedir(alvo)
            corpo = json.dumps({"ok": True, "alvo": alvo, "na_fila": bool(ocupado)}).encode()
            self.send_response(202)
            self._cors(origem)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(corpo)

        def log_message(self, *a):  # sem eco no console (pythonw não tem um)
            pass
    return Tratador


def servir(porta: int, pedidos: Pedidos, log):
    """Sobe o endereço local numa thread; None se a porta estiver ocupada."""
    from .monitores import PASTA_MONITORES
    existe = lambda id_: (PASTA_MONITORES / f"{id_}.toml").exists()
    try:
        srv = ThreadingHTTPServer(("127.0.0.1", porta), tratador(pedidos, existe))
    except OSError as e:
        log(f"Vigia: endereço local 127.0.0.1:{porta} indisponível ({e}); o botão usa o GitHub.")
        return None
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    log(f"Vigia: atendendo o botão da página em 127.0.0.1:{porta}.")
    return srv


def atender_locais(pedidos: Pedidos, log) -> None:
    fila = pedidos.tirar()
    if not fila:
        return
    alvos = [TODOS] if TODOS in fila else sorted(fila)
    for alvo in alvos:
        pedidos.rodando = alvo
        log("Vigia: botão da página — " + ("todos os monitores." if alvo == TODOS else f"monitor {alvo}."))
        try:
            rodar_monitor("--todos") if alvo == TODOS else rodar_monitor("--monitor", alvo)
        finally:
            pedidos.rodando = None


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


def ultima_rodada() -> datetime | None:
    """A consulta mais recente de qualquer monitor (o estado.json de cada um)."""
    datas = []
    for est in [DADOS / "estado.json", *DADOS.glob("*/estado.json")]:  # o freezer mora na raiz de dados/
        try:
            datas.append(datetime.fromisoformat(json.loads(est.read_text(encoding="utf-8"))["ultima_execucao"]))
        except (OSError, ValueError, KeyError, TypeError):
            continue
    return max(datas, default=None)


def atrasada(agora: datetime, ultima: datetime | None, tentou: datetime | None, horas: float) -> bool:
    """Passou um dia sem rodada? E sem insistir: depois de uma tentativa, espera 2 h pela próxima
    (sem rede, a rodada não grava data nenhuma e o vigia a dispararia a cada volta)."""
    if not horas or (tentou and agora - tentou < timedelta(hours=2)):
        return False
    return ultima is None or agora - ultima >= timedelta(hours=horas)


def vigiar(repo: str, minutos: float, log, porta: int = 0, recuperar_horas: float = 24) -> None:
    trava = travar()
    if trava is None:
        log("Vigia: já há outro rodando; este sai.")
        return
    log(f"Vigia: olhando {repo} a cada {minutos:g} min.")
    pedidos = Pedidos()
    if porta:
        servir(porta, pedidos, log)
    ja_avisado: set[str] = set()
    falhando = False
    tentou = None
    while True:
        # o notebook passa dias em espera, com este processo congelado; na primeira volta
        # depois de acordar, se o dia passou sem rodada, ela sai agora (--logon respeita
        # o intervalo de cada monitor, e a trava da rodada barra uma segunda em paralelo)
        agora = datetime.now()
        if atrasada(agora, ultima_rodada(), tentou, recuperar_horas):
            log(f"Vigia: nenhuma rodada há {recuperar_horas:g} h ou mais; rodando agora.")
            tentou = agora
            rodar_monitor("--logon")
        atender_locais(pedidos, log)  # o botão local vem antes do GitHub, que pode estar fora
        try:
            uma_volta(repo, log, ja_avisado)
            if falhando:
                log("Vigia: GitHub respondendo de novo.")
            falhando = False
        except Exception as exc:  # sem rede, gh fora do ar: tenta de novo na próxima volta
            if not falhando:
                log(f"Vigia: consulta falhou ({exc!r}); sigo tentando.")
            falhando = True
        atender_locais(pedidos, log)
        pedidos.evento.wait(minutos * 60)  # o botão local acorda antes
        pedidos.evento.clear()
