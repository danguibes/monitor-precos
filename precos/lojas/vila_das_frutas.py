"""Vila das Frutas (plataforma osuper): pelo texto da página, no navegador do monitor.

A entrega só aparece com a conta logada no perfil do monitor
(py monitor.py --configurar viladasfrutas). Logado e com o modo Entrega, o
cabeçalho mostra o próximo horário e a taxa ("Próximo: Sáb • 8h às 8:59 •
R$ 15,00") e o frete grátis a partir de certo valor. A busca fica em
/busca/<termo>, e cada produto aparece como "R$ X / un / título" — o preço
vem antes do título, e na promoção o preço antigo vem antes, numa linha só
("R$ 8,99 un").

O cabeçalho logado traz também o endereço completo da conta: nada dele sai
daqui além da taxa e do horário.
"""
from __future__ import annotations

import re
import time
import urllib.parse

from ..base import NUM, num, oferta
from ..navegador import ir, texto

BASE = "https://www.viladasfrutas.com.br"
_PRECO = re.compile(r"^R\$\s*" + NUM + r"$")
_RUIDO = re.compile(r"^(360°|Oferta|Patrocinado|EXCLUSIVO ONLINE|-?\d+%)$", re.I)


def ler_entrega(t: str):
    """{"frete", "prazo", "gratis_acima"} do cabeçalho, ou um texto de erro.

    Erro quando a conta não está logada ou o modo é Retirada: nesses casos a
    taxa do cabeçalho não é a de entregar em casa.
    """
    if re.search(r"Entre\s*\|\s*Cadastre-se", t):
        return "pede login — rode 'py monitor.py --configurar viladasfrutas' e entre na conta"
    i = t.find("Próximo:")
    if i < 0 or not re.search(r"\nEntrega\n", t[:i]):
        return "o modo não é Entrega — escolha Entrega no cabeçalho, com --configurar viladasfrutas"
    trecho = t[i + len("Próximo:"): i + 120]
    m = re.search(r"R\$\s*" + NUM, trecho)
    if not m:
        return "não achei a taxa de entrega no cabeçalho"
    prazo = re.sub(r"[\s•|]+", " ", trecho[:m.start()]).strip()
    g = re.search(r"Frete Grátis a partir de R\$\s*" + NUM, t)
    return {"frete": num(m.group(1)), "prazo": prazo, "gratis_acima": num(g.group(1)) if g else None}


def ler_busca(t: str):
    """[(título, preço)] da página de busca, na ordem da página."""
    ini = t.find("Encontramos")
    # "Categorias" aparece duas vezes: no filtro, logo depois de "Encontramos", e no
    # rodapé, depois da lista. A lista termina na última.
    fim = t.rfind("\nCategorias\n")
    fim = fim if fim > ini else -1
    linhas = [l.strip() for l in t[ini if ini >= 0 else 0: fim if fim > 0 else len(t)].split("\n")]
    linhas = [l for l in linhas if l and not _RUIDO.match(l)]
    res, preco = [], None
    for i, l in enumerate(linhas):
        m = _PRECO.match(l)
        if m:
            preco = num(m.group(1))  # o último R$ antes de "un" é o preço atual
        elif l == "un" and preco is not None and i + 1 < len(linhas):
            titulo = linhas[i + 1]
            if not _PRECO.match(titulo) and not titulo.startswith("R$"):
                res.append((titulo, preco))
            preco = None
    return res


def coletar(page, cfg, produtos, data, filtros, erros):
    if not ir(page, BASE + "/", espera=5):
        erros.append("Vila das Frutas: não abriu a página")
        return []
    entrega = ler_entrega(texto(page))
    if isinstance(entrega, str):
        erros.append(f"Vila das Frutas: {entrega}")
        return []
    ofertas = []
    for prod in produtos:
        url = f"{BASE}/busca/{urllib.parse.quote(prod['busca'])}"
        if not ir(page, url, espera=3):
            erros.append(f"Vila das Frutas: busca {prod['busca']} não abriu")
            continue
        try:
            page.wait_for_selector("text=Encontramos", timeout=10000)
        except Exception:
            time.sleep(2)
        for titulo, preco in ler_busca(texto(page)):
            if filtros(titulo, prod):
                ofertas.append(oferta("Vila das Frutas", prod["modelo"], titulo, "Vila das Frutas",
                                      preco, None, entrega["frete"], entrega["prazo"], url, data,
                                      sku=titulo))  # sem código na página: o título identifica o produto
    return ofertas
