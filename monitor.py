"""
Monitor de preços — preço + frete para o CEP configurado.

Uso:
  py monitor.py              -> roda o freezer agora (ignora o intervalo mínimo)
  py monitor.py --monitor agua-com-gas -> roda outro monitor (monitores/<id>.json)
  py monitor.py --todos      -> roda todos os monitores
  py monitor.py --logon      -> modo "ao ligar o computador": espera a rede,
                                roda todos, respeita o intervalo mínimo de cada um
                                e só abre o relatório se algum preço caiu
  py monitor.py --relatorio  -> só regera e abre o relatório
  py monitor.py --configurar -> abre o navegador do monitor para login (ML,
                                Shopee, Vila das Frutas) e CEP; feche a janela ao terminar
  py monitor.py --configurar viladasfrutas -> o mesmo, só com as páginas que contêm o termo
  py monitor.py --sem-navegador -> só as lojas por API (rápido)
  py monitor.py --publicar   -> só republica os relatórios no GitHub Pages
  py monitor.py --pedidos    -> atende os pedidos do formulário e roda já os monitores criados
  py monitor.py --nao-publicar -> coleta sem publicar

Tudo o que é gerado (histórico, relatório, log, perfil do navegador) fica em dados/.
"""
from __future__ import annotations

import os
import sys
import time
import webbrowser
from datetime import datetime, timedelta
from pathlib import Path

from precos import monitores as mon
from precos.base import carregar_json, log, salvar_json
from precos.historico import gravar_historico
from precos.historico_pagina import gerar_historico
from precos.relatorio import gerar_relatorio, houve_queda


def abrir(caminho: Path):
    try:
        if hasattr(os, "startfile"):
            os.startfile(str(caminho))  # Windows
        else:
            webbrowser.open(caminho.as_uri())
    except OSError:
        pass


def escolher(monitores, argv):
    if "--todos" in argv or "--logon" in argv:
        return monitores
    if "--monitor" in argv:
        i = argv.index("--monitor")
        nome = argv[i + 1] if i + 1 < len(argv) else ""
        achados = [m for m in monitores if m["id"] == nome]
        if not achados:
            log(f"Monitor '{nome}' não existe. Há: {', '.join(m['id'] for m in monitores)}.")
        return achados
    return monitores[:1]  # o freezer


def vencido(m) -> bool:
    """No logon, cada monitor respeita o próprio intervalo mínimo."""
    ultima = carregar_json(m["estado"], {}).get("ultima_execucao")
    horas = float(m["cfg"].get("intervalo_minimo_horas", 6))
    if ultima and datetime.now() - datetime.fromisoformat(ultima) < timedelta(hours=horas):
        log(f"[{m['id']}] Pulando: última consulta há menos de {horas:g} h.")
        return False
    return True


def ler_augustinus():
    """As compras da casa no Augustinus, uma vez por rodada; None se não há acesso (o monitor segue)."""
    aug = mon.ler_toml(mon.LOCAL, obrigatorio=False).get("augustinus")
    if not aug:
        return None
    from precos.augustinus import ler_compras
    try:
        compras = ler_compras(aug)
    except Exception as exc:  # banco fora do ar ou senha trocada: fica a referência anterior
        log(f"Augustinus: não li as compras ({exc!r}); mantenho a referência anterior.")
        return None
    log(f"Augustinus: {len(compras)} compras lidas.")
    return {"compras": compras, "app": aug.get("app", "")}


def atualizar_referencia(m, estado, aug) -> None:
    from precos.augustinus import referencia
    if aug is None:
        return
    ref = referencia(aug["compras"], m["cfg"])
    if ref:
        ref["app"] = aug["app"]
    estado["referencia_augustinus"] = ref


def rodar(m, argv, aug=None) -> None:
    cfg, estado = m["cfg"], carregar_json(m["estado"], {})
    modo_logon = "--logon" in argv

    from precos import coleta

    log(f"[{m['id']}] Coletando...")
    ofertas, erros = coleta.coletar_tudo(cfg, estado, log, com_navegador="--sem-navegador" not in argv)
    for x in erros:
        log("  aviso: " + x)
    log(f"{len(ofertas)} ofertas com entrega para o CEP.")
    if ofertas:
        gravar_historico(ofertas, m["historico"])
        estado["ultima_execucao"] = datetime.now().isoformat(timespec="seconds")
    estado["avisos"] = erros  # a página publicada mostra os avisos da última rodada
    atualizar_referencia(m, estado, aug)
    salvar_json(m["estado"], estado)

    res = gerar_relatorio(cfg, erros, m["relatorio"], m["historico"],
                          referencia=estado.get("referencia_augustinus"))
    gerar_historico(cfg, m["relatorio"].parent / "historico.html", m["historico"], volta=m["relatorio"].name)
    regra = cfg.get("abrir_relatorio", "quando_baixar")
    if not modo_logon or regra == "sempre" or (regra == "quando_baixar" and houve_queda(res)):
        abrir(m["relatorio"])


def atualizar_do_github() -> None:
    """No logon, puxa o que foi editado no GitHub (um monitor novo, uma regra) antes de rodar."""
    import subprocess
    from precos.base import RAIZ
    r = subprocess.run(["git", "pull", "--ff-only", "-q"], cwd=RAIZ, capture_output=True, text=True)
    if r.returncode:
        log(f"git pull falhou (segue com o que há aqui): {r.stderr.strip()[:200]}")


def atender_pedidos() -> list[str]:
    """Pedidos do formulário do GitHub viram monitores antes de a rodada carregar a lista.

    Devolve os ids criados ou alterados: eles rodam já, sem esperar o intervalo.
    """
    from precos import pedidos
    from precos.base import salvar_json
    from precos.publicar import AVISOS_PEDIDOS, repo_web
    repo = repo_web()
    if not repo:
        return []
    try:
        avisos, prontos = pedidos.atender(repo.removeprefix("https://github.com/"), log)
    except Exception as exc:  # um pedido estranho nunca derruba a coleta
        log(f"Pedidos: ERRO {exc!r}")
        return []
    salvar_json(AVISOS_PEDIDOS, avisos)
    return prontos


def publicar_se_ligado(monitores, argv) -> None:
    if "--nao-publicar" in argv or not monitores[0]["cfg"].get("publicar"):
        return
    from precos.publicar import publicar
    try:
        publicar(monitores, mon.ler_toml(mon.LOCAL, obrigatorio=False), log)
    except Exception as exc:  # publicar nunca derruba a coleta
        log(f"Publicação: ERRO {exc!r}")


def main(argv):
    if "--logon" in argv:
        atualizar_do_github()
    novos = []
    if {"--logon", "--todos", "--pedidos"} & set(argv):
        novos = atender_pedidos()
        if "--pedidos" in argv and not novos:
            return 0
    try:
        monitores = mon.carregar(precisa_cep="--relatorio" not in argv)
    except mon.ConfiguracaoInvalida as e:
        log(f"Configuração: {e}.")
        return 1
    if not monitores:
        log("Nenhum monitor em monitores/.")
        return 1

    if "--configurar" in argv:
        from precos.navegador import configurar
        i = argv.index("--configurar")
        filtro = argv[i + 1] if i + 1 < len(argv) and not argv[i + 1].startswith("--") else ""
        configurar(monitores[0]["cfg"], filtro)
        return 0

    if "--publicar" in argv:  # só republica, sem coletar
        publicar_se_ligado(monitores, [])
        return 0

    escolhidos = escolher(monitores, argv)
    if "--relatorio" in argv:
        for m in escolhidos:
            gerar_relatorio(m["cfg"], [], m["relatorio"], m["historico"],
                            referencia=carregar_json(m["estado"], {}).get("referencia_augustinus"))
            gerar_historico(m["cfg"], m["relatorio"].parent / "historico.html", m["historico"],
                            volta=m["relatorio"].name)
            abrir(m["relatorio"])
        return 0

    if "--pedidos" in argv:  # criado ou alterado pelo formulário: a primeira consulta é já
        escolhidos = [m for m in monitores if m["id"] in novos]
    if "--logon" in argv:  # o monitor recém-pedido roda mesmo dentro do intervalo
        escolhidos = [m for m in escolhidos if m["id"] in novos or vencido(m)]
        if escolhidos:
            time.sleep(45)  # dá tempo da rede subir depois do login
    aug = ler_augustinus() if escolhidos else None
    for m in escolhidos:
        try:
            rodar(m, argv, aug)
        except Exception as exc:  # um monitor quebrado não impede os outros
            log(f"[{m['id']}] ERRO: {exc!r}")
    if escolhidos:
        publicar_se_ligado(monitores, argv)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except Exception as exc:  # nunca deixa o logon com erro feio
        log(f"ERRO: {exc!r}")
        sys.exit(1)
