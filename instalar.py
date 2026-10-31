"""
Instalador do monitor de preços (só Python: este notebook bloqueia .bat e PowerShell).

Rode uma vez, de dentro da pasta do monitor:
    py instalar.py          (ou: python instalar.py)

Ele:
  1. instala o Playwright (controle do navegador);
  2. instala o Chromium do Playwright se não houver Google Chrome;
  3. coloca um lançador .pyw na pasta Inicializar do Windows
     (roda o monitor a cada login, sem janela de console);
  4. abre o navegador do monitor para login no Mercado Livre e na Shopee;
  5. faz a primeira consulta.

Para só refazer o lançador (depois de mover a pasta): py instalar.py --lancador
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
    return (
        "import runpy, sys\n"
        f"pasta = {str(PASTA)!r}\n"
        "sys.path.insert(0, pasta)\n"
        "sys.argv = [pasta + r'\\monitor.py', '--logon']\n"
        "import os; os.chdir(pasta)\n"
        "runpy.run_path(pasta + r'\\monitor.py', run_name='__main__')\n"
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
        return
    if "--lancador" in sys.argv:
        criar_lancador()
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

    print("[3/5] Lançador na pasta Inicializar...")
    criar_lancador()

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
