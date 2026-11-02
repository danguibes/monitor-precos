"""
Instalador do monitor de preços (só Python: este notebook bloqueia .bat e PowerShell).

Rode uma vez, de dentro da pasta do monitor:
    py instalar.py          (ou: python instalar.py)

Ele:
  1. instala o Playwright (controle do navegador);
  2. instala o Chromium do Playwright se não houver Google Chrome;
  3. coloca um lançador .pyw na pasta Inicializar do Windows
     (roda o monitor a cada login, sem janela de console) e agenda uma rodada
     diária às 6h que acorda o notebook, se estiver na tomada;
  4. abre o navegador do monitor para login no Mercado Livre e na Shopee;
  5. faz a primeira consulta.

Para só refazer o lançador (depois de mover a pasta): py instalar.py --lancador
Para só (re)criar a tarefa diária: py instalar.py --agendar [HH:MM]
Para desinstalar: py instalar.py --remover
"""
import os
import subprocess
import sys
from pathlib import Path

PASTA = Path(__file__).resolve().parent
NOME_LANCADOR = "Monitor de Precos.pyw"
# nome da primeira versão, que apontava para C:\Claude\monitor-freezer: sai ao instalar
LANCADORES_ANTIGOS = ["Monitor Freezer.pyw"]


def pasta_inicializar() -> Path:
    appdata = os.environ.get("APPDATA")
    if not appdata:
        sys.exit("Não achei a variável APPDATA (isto é Windows?).")
    return Path(appdata) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"


def tem_chrome() -> bool:
    candidatos = [
        Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Google/Chrome/Application/chrome.exe",
        Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")) / "Google/Chrome/Application/chrome.exe",
        Path(os.environ.get("LOCALAPPDATA", "")) / "Google/Chrome/Application/chrome.exe",
    ]
    return any(c.exists() for c in candidatos)


def rodar(*args) -> int:
    print("  >", " ".join(str(a) for a in args))
    return subprocess.call([sys.executable, *map(str, args)], cwd=PASTA)


def lancador() -> str:
    # Roda o monitor no mesmo processo, sem console (extensão .pyw → pythonw).
    # Primeiro a rodada do logon; depois o vigia fica olhando o GitHub até desligar.
    # Mudou este texto? `py instalar.py --lancador` regrava o da pasta Inicializar.
    return (
        "import runpy, sys\n"
        f"pasta = {str(PASTA)!r}\n"
        "sys.path.insert(0, pasta)\n"
        "import os; os.chdir(pasta)\n"
        "for modo in ('--logon', '--vigiar'):\n"
        "    sys.argv = [pasta + r'\\monitor.py', modo]\n"
        "    try:\n"
        "        runpy.run_path(pasta + r'\\monitor.py', run_name='__main__')\n"
        "    except SystemExit:\n"
        "        pass\n"
    )


def remover(nomes=None):
    removeu = False
    for nome in nomes or [NOME_LANCADOR, *LANCADORES_ANTIGOS]:
        alvo = pasta_inicializar() / nome
        if alvo.exists():
            alvo.unlink()
            print("  Removido:", alvo)
            removeu = True
    if not removeu and nomes is None:
        print("Nada para remover em", pasta_inicializar())


def criar_lancador():
    destino = pasta_inicializar()
    destino.mkdir(parents=True, exist_ok=True)
    remover(LANCADORES_ANTIGOS)  # senão o monitor velho também roda no logon
    (destino / NOME_LANCADOR).write_text(lancador(), encoding="utf-8")
    print("  Criado:", destino / NOME_LANCADOR)


NOME_TAREFA = "Monitor de Precos - rodada diaria"
HORA_TAREFA = "06:00"


def tarefa_xml(hora: str = HORA_TAREFA) -> str:
    """A tarefa do Agendador: todo dia, acordando o notebook da espera, só na tomada.

    O lançador do logon só roda quando alguém entra no Windows, e o notebook passa
    dias em espera sem um logon novo. Esta tarefa cobre isso: o Windows acorda o
    notebook (só na tomada: na bateria os despertadores estão desligados, e é bom
    que fiquem), o monitor pede para ele não dormir durante a rodada e o devolve à
    espera ao terminar. Sem tomada às 6h, quem cobre é a recuperação do vigia.
    Roda na sessão do Danilo (InteractiveToken): precisa do perfil do Chrome e não
    guarda senha nenhuma.
    """
    from datetime import date, timedelta
    from xml.sax.saxutils import escape
    pythonw = Path(sys.executable).with_name("pythonw.exe")
    usuario = f'{os.environ.get("USERDOMAIN", "")}\\{os.environ.get("USERNAME", "")}'.lstrip("\\")
    inicio = f"{date.today() + timedelta(days=1)}T{hora}:00"
    return f"""<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.4" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <RegistrationInfo><Description>Monitor de preços: uma rodada por dia, acordando o notebook se estiver na tomada. Criada por instalar.py --agendar.</Description></RegistrationInfo>
  <Triggers><CalendarTrigger><StartBoundary>{inicio}</StartBoundary><Enabled>true</Enabled>
    <ScheduleByDay><DaysInterval>1</DaysInterval></ScheduleByDay></CalendarTrigger></Triggers>
  <Principals><Principal id="Author"><UserId>{escape(usuario)}</UserId><LogonType>InteractiveToken</LogonType>
    <RunLevel>LeastPrivilege</RunLevel></Principal></Principals>
  <Settings>
    <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>
    <DisallowStartIfOnBatteries>true</DisallowStartIfOnBatteries>
    <StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>
    <StartWhenAvailable>false</StartWhenAvailable>
    <RunOnlyIfNetworkAvailable>false</RunOnlyIfNetworkAvailable>
    <IdleSettings><StopOnIdleEnd>false</StopOnIdleEnd><RestartOnIdle>false</RestartOnIdle></IdleSettings>
    <WakeToRun>true</WakeToRun>
    <ExecutionTimeLimit>PT2H</ExecutionTimeLimit>
    <Enabled>true</Enabled>
  </Settings>
  <Actions Context="Author"><Exec><Command>{escape(str(pythonw))}</Command>
    <Arguments>monitor.py --logon --sem-abrir</Arguments>
    <WorkingDirectory>{escape(str(PASTA))}</WorkingDirectory></Exec></Actions>
</Task>
"""


def agendar(hora: str = HORA_TAREFA) -> None:
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        xml = Path(tmp) / "tarefa.xml"
        xml.write_text(tarefa_xml(hora), encoding="utf-16")
        r = subprocess.run(["schtasks", "/Create", "/TN", NOME_TAREFA, "/XML", str(xml), "/F"],
                           capture_output=True, text=True)
    print(f"  Tarefa agendada: {NOME_TAREFA}, todo dia às {hora}." if r.returncode == 0
          else f"  A tarefa não foi criada: {(r.stderr or r.stdout).strip()}")


def desagendar() -> None:
    r = subprocess.run(["schtasks", "/Delete", "/TN", NOME_TAREFA, "/F"], capture_output=True, text=True)
    if r.returncode == 0:
        print("  Removida a tarefa:", NOME_TAREFA)


def criar_local():
    """local.toml guarda o CEP e fica fora do git; o instalador pergunta uma vez."""
    import re
    local = PASTA / "local.toml"
    if local.exists():
        print("  local.toml já existe; mantido.")
        return
    while True:
        cep = input("  Qual o CEP de entrega (00000-000)? ").strip()
        if re.fullmatch(r"\d{5}-?\d{3}", cep):
            break
        print("  CEP inválido.")
    cep = cep if "-" in cep else cep[:5] + "-" + cep[5:]
    modelo = (PASTA / "local.exemplo.toml").read_text(encoding="utf-8")
    local.write_text(modelo.replace('cep = "00000-000"', f'cep = "{cep}"'), encoding="utf-8")
    print("  Criado: local.toml (fora do git). Edite a lista nao_publicar com rua e número.")


def main():
    if "--remover" in sys.argv:
        remover()
        desagendar()
        return
    if "--lancador" in sys.argv:
        criar_lancador()
        return
    if "--agendar" in sys.argv:
        i = sys.argv.index("--agendar")
        hora = sys.argv[i + 1] if i + 1 < len(sys.argv) else HORA_TAREFA
        agendar(hora)
        return

    print("[0/5] CEP de entrega...")
    criar_local()

    print("[1/5] Instalando o Playwright e o pg8000...")
    if rodar("-m", "pip", "install", "--upgrade", "--quiet", "-r", PASTA / "requirements.txt") != 0:
        sys.exit("Falhou o pip install (playwright, pg8000).")

    print("[2/5] Navegador...")
    if tem_chrome():
        print("  Google Chrome encontrado; será usado.")
    else:
        print("  Chrome não encontrado; baixando o Chromium do Playwright...")
        rodar("-m", "playwright", "install", "chromium")

    print("[3/5] Lançador na pasta Inicializar e tarefa diária...")
    criar_lancador()
    agendar()

    print("\n[4/5] Vai abrir o navegador do monitor:")
    print("  - entre na sua conta do Mercado Livre e da Shopee;")
    print("  - se Magalu, Casas Bahia ou Carrefour pedirem, informe o CEP;")
    print("  - feche a janela do navegador quando terminar.")
    input("  Tecle Enter para abrir... ")
    rodar(PASTA / "monitor.py", "--configurar")

    print("\n[5/5] Primeira consulta (leva alguns minutos)...")
    rodar(PASTA / "monitor.py")
    print("\nPronto. O monitor roda a cada login (no máximo a cada 6 h; ajuste no config.toml).")
    print("Para desinstalar: py instalar.py --remover")


if __name__ == "__main__":
    main()
