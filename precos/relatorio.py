"""Relatório HTML: um card por modelo e a tabela de todas as ofertas da última rodada."""
from __future__ import annotations

import html

from .base import HISTORICO, RELATORIO, brl, brl_un
from .historico import ler_historico
from .unidades import kit_ambiguo, sufixo, unidade_de_comparacao, unidades_na_oferta


ESTILO = """:root{--bg:#f6f5f2;--card:#fff;--tx:#1d1d1b;--mut:#6b6a66;--ln:#e3e1dc;--ok:#1f7a4d;--bad:#b3261e;--ac:#2f5d8a}
@media (prefers-color-scheme:dark){:root{--bg:#151514;--card:#1f1f1d;--tx:#ecebe7;--mut:#a3a19b;--ln:#33322f;--ok:#5fc48f;--bad:#f08a80;--ac:#8db7e0}}
body{margin:0;background:var(--bg);color:var(--tx);font:15px/1.45 system-ui,Segoe UI,sans-serif}
main{max-width:1080px;margin:0 auto;padding:24px 16px}
h1{font-size:22px;margin:0 0 4px} .sub{color:var(--mut);margin:0 0 20px}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:14px}
.card{background:var(--card);border:1px solid var(--ln);border-radius:12px;padding:14px 16px}
.card header{display:flex;justify-content:space-between;gap:8px;align-items:baseline}
h2{font-size:16px;margin:0} .meta,.det{color:var(--mut);font-size:13px}
.total{font-size:24px;font-weight:650;margin:8px 0 2px} .spark{color:var(--ac);margin-top:6px}
.desce{color:var(--ok);font-size:14px} .sobe{color:var(--bad);font-size:14px}
.selo{background:var(--ok);color:var(--card);border-radius:99px;font-size:11px;padding:2px 8px;white-space:nowrap}
a{color:var(--ac)} table{width:100%;border-collapse:collapse;font-size:13px;margin-top:8px}
th,td{text-align:left;padding:6px 8px;border-bottom:1px solid var(--ln)} .n{text-align:right;white-space:nowrap}
.tab{overflow-x:auto;background:var(--card);border:1px solid var(--ln);border-radius:12px;margin-top:22px;padding:6px 8px}
.avisos{color:var(--mut);font-size:13px}
button.botao{font:inherit;cursor:pointer} .atualizar{margin:8px 0 0}
.botao{display:inline-block;background:var(--ac);color:var(--card);padding:8px 14px;border-radius:10px;text-decoration:none;font-weight:600}
.botao.secundario{background:transparent;color:var(--ac);border:1.5px solid var(--ac)}
.kit{display:inline-block;border:1px solid var(--bad);color:var(--bad);border-radius:99px;font-size:11px;padding:0 7px;margin-left:4px;white-space:nowrap;cursor:help}
.selo-aug{display:inline-block;background:var(--ok);color:var(--card);border-radius:99px;font-size:12px;font-weight:600;padding:2px 9px;margin:4px 0 2px}
.topo{display:flex;flex-wrap:wrap;gap:12px 24px;align-items:flex-start;justify-content:space-between;margin-bottom:20px}
.topo .sub{margin:0} .topo>div{flex:1 1 340px}
.aug{background:var(--card);border:1px solid var(--ln);border-radius:12px;padding:10px 14px;font-size:13px;flex:0 1 360px}
.aug b{font-size:15px} .aug ul{margin:6px 0 0;padding-left:18px} .aug li{margin:2px 0}
"""


ORDENAR = r"""<script>
// Clique no cabeçalho ordena a coluna; outro clique inverte. "—" e vazio vão para o fim.
document.querySelectorAll("table").forEach(tb => {
  const ths = [...tb.querySelectorAll("thead th")];
  ths.forEach((th, i) => {
    th.style.cursor = "pointer"; th.title = "ordenar por esta coluna";
    th.addEventListener("click", () => {
      const asc = th.dataset.ord !== "asc";
      ths.forEach(x => { delete x.dataset.ord; x.textContent = x.textContent.replace(/ [▲▼]$/, ""); });
      th.dataset.ord = asc ? "asc" : "desc"; th.textContent += asc ? " ▲" : " ▼";
      const valor = r => {
        const t = (r.cells[i] ? r.cells[i].textContent : "").trim();
        if (t === "" || t === "—") return null;
        if (/^(R\$\s*)?-?[\d.]+(,\d+)?/.test(t)) {
          const n = parseFloat(t.replace(/^R\$\s*/, "").replace(/\./g, "").replace(",", "."));
          if (!isNaN(n)) return n;
        }
        return t.toLowerCase();
      };
      const corpo = tb.tBodies[0];
      [...corpo.rows].sort((a, b) => {
        const x = valor(a), y = valor(b);
        if (x === null) return 1; if (y === null) return -1;
        if (typeof x !== typeof y) return typeof x === "number" ? -1 : 1;
        return (x < y ? -1 : x > y ? 1 : 0) * (asc ? 1 : -1);
      }).forEach(r => corpo.appendChild(r));
    });
  });
});
</script>"""


def sparkline(valores: list[float], largura=160, altura=36) -> str:
    if len(valores) < 2:
        return ""
    lo, hi = min(valores), max(valores)
    faixa = (hi - lo) or 1
    pts = []
    for i, v in enumerate(valores):
        x = 2 + i * (largura - 4) / (len(valores) - 1)
        y = altura - 3 - (v - lo) / faixa * (altura - 6)
        pts.append(f"{x:.1f},{y:.1f}")
    ux, uy = pts[-1].split(",")
    return (f'<svg width="{largura}" height="{altura}" viewBox="0 0 {largura} {altura}" '
            f'aria-label="histórico do menor total"><polyline fill="none" stroke="currentColor" '
            f'stroke-width="1.6" points="{" ".join(pts)}"/><circle cx="{ux}" cy="{uy}" r="2.6" '
            f'fill="currentColor"/></svg>')


def por_unidade(cfg) -> bool:
    """Sem pack montado, pacotes de tamanhos diferentes só se comparam por unidade (lenço: 16, 50, 88)."""
    return unidade_de_comparacao(cfg) is not None and not (cfg.get("regras") or {}).get("montar_pack")


def valor(l, cfg):
    """O que decide "a melhor oferta": o total, ou o total por unidade quando os pacotes variam."""
    if not por_unidade(cfg):
        return l["total_pix"]
    n = unidades_na_oferta(l["produto"], cfg)
    return l["total_pix"] / n if n else None


def analisar(historico, cfg):
    """Para cada modelo: melhor oferta da última rodada, da anterior e mínimo histórico.

    Com pacotes de tamanhos diferentes a conta é por unidade, e o anúncio sem
    contagem no título não ganha (como o sem frete): não dá para dizer quanto custa cada um.
    """
    rodadas = sorted({l["data"] for l in historico})
    ultima = rodadas[-1] if rodadas else None
    anterior = rodadas[-2] if len(rodadas) > 1 else None
    res = []
    if cfg.get("modo") == "descoberta":  # um card por loja, as que já apareceram
        grupos = [{"modelo": m} for m in sorted({l["modelo"] for l in historico})]
    else:
        grupos = cfg["produtos"]
    for prod in grupos:
        m = prod["modelo"]
        linhas = [dict(l, valor=valor(l, cfg)) for l in historico if l["modelo"] == m and l["total_pix"] is not None]
        atual = [l for l in linhas if l["data"] == ultima]
        antes = [l for l in linhas if l["data"] == anterior]
        # ofertas sem frete informado (Shopee, às vezes ML) não "ganham" o ranking
        com_frete = lambda ls: [l for l in ls if l.get("frete") is not None and l["valor"] is not None]
        contaveis = lambda ls: [l for l in ls if l["valor"] is not None]
        atual_v = com_frete(atual) or contaveis(atual)
        antes_v = com_frete(antes) or contaveis(antes)
        linhas_v = com_frete(linhas) or contaveis(linhas)
        melhor = min(atual_v, key=lambda l: l["valor"]) if atual_v else None
        melhor_antes = min((l["valor"] for l in antes_v), default=None)
        minimo = min(linhas_v, key=lambda l: l["valor"]) if linhas_v else None
        por_dia = {}
        for l in linhas_v:
            d = l["data"][:10]
            por_dia[d] = min(por_dia.get(d, 1e12), l["valor"])
        serie = [por_dia[d] for d in sorted(por_dia)]
        res.append({"prod": prod, "melhor": melhor, "antes": melhor_antes,
                    "minimo": minimo, "serie": serie,
                    "ofertas": sorted(atual, key=lambda l: (l["valor"] is None, l["valor"] or 0, l["total_pix"]))})
    return ultima, res


def aviso_kit(produto: str, cfg, curto=False) -> str:
    """Kit ou "N pacotes": a contagem pode ser do kit ou de cada pacote, e o vendedor não diz.

    A conta usa o número do título sem multiplicar (o menor total, que nunca faz o
    kit parecer mais barato do que é); a etiqueta avisa para conferir na loja.
    """
    if unidade_de_comparacao(cfg) is None or not kit_ambiguo(produto):
        return ""
    n = unidades_na_oferta(produto, cfg)
    dica = (f"Anúncio de kit: contei {n:g} no total. Se forem {n:g} em cada pacote, "
            f"cada unidade sai mais barata do que aparece aqui. Confira na loja.")
    return f'<span class="kit" title="{html.escape(dica)}">⚠{"" if curto else " kit: confira a quantidade"}</span>'


# O botão "Atualizar" fala primeiro com o vigia no próprio notebook (127.0.0.1, ver
# vigia.py); sem resposta em 2,5 s — outro aparelho, notebook dormindo — abre o
# formulário do GitHub, que o vigia atende quando puder.
SCRIPT_ATUALIZAR = r"""<script>
document.querySelectorAll("[data-atualizar]").forEach(b => b.addEventListener("click", async () => {
  const alvo = b.dataset.alvo || "", aviso = b.parentElement.querySelector(".resposta");
  const url = "http://127.0.0.1:" + b.dataset.porta + "/atualizar" + (alvo ? "/" + alvo : "");
  b.disabled = true; aviso.textContent = "Chamando o notebook...";
  try {
    const c = new AbortController(); const t = setTimeout(() => c.abort(), 2500);
    const r = await fetch(url, {method: "POST", signal: c.signal}); clearTimeout(t);
    if (!r.ok) throw new Error("HTTP " + r.status);
    const j = await r.json();
    aviso.textContent = (j.na_fila ? "Na fila: o notebook termina a rodada em curso e emenda esta. "
                                    : "Começou no notebook. ")
      + (alvo ? "Este monitor leva alguns minutos" : "Todos os monitores levam perto de uma hora")
      + "; a página se republica sozinha ao fim — recarregue depois.";
  } catch (e) {
    const w = window.open(b.dataset.github, "_blank", "noopener");
    aviso.innerHTML = "O notebook não respondeu daqui (outro aparelho, ou ele está dormindo). "
      + (w ? "Abri o pedido no GitHub: é só enviar." : '<a href="' + b.dataset.github + '" target="_blank" rel="noopener">Abrir o pedido no GitHub</a>.');
  } finally { b.disabled = false; }
}));
</script>"""


def botao_atualizar(porta: int, link_github: str, alvo: str = "", rotulo: str = "↻ Atualizar agora") -> str:
    e = html.escape
    if not porta:
        return (f'<a class="botao secundario" href="{e(link_github)}" target="_blank" rel="noopener">{e(rotulo)}</a>')
    return (f'<button type="button" class="botao secundario" data-atualizar data-porta="{int(porta)}" '
            f'data-alvo="{e(alvo)}" data-github="{e(link_github)}">{e(rotulo)}</button>')


def selo_augustinus(oferta, ref, cfg) -> str:
    """Só a marca, no card: a conta e o link ficam uma vez no quadro do topo."""
    from .augustinus import comparar
    cmp = comparar(oferta, ref, cfg)
    return '<div><span class="selo-aug">▼ abaixo do que você paga</span></div>' if cmp and cmp["nivel"] == "forte" else ""


def quadro_augustinus(ref, cfg, melhores) -> str:
    """O que a casa paga, uma vez por página: a mediana na unidade do monitor, a melhor oferta
    daqui na mesma unidade e um link para cada conceito do Augustinus (mais de um quando as
    compras se espalham por vários, como o papel)."""
    from .augustinus import comparar
    if unidade_de_comparacao(cfg) is None:
        return ""
    e = html.escape
    if not ref:
        return ('<aside class="aug"><b>Augustinus</b>'
                '<div class="det">Nenhuma compra deste item no último ano.</div></aside>')
    un = sufixo(cfg)
    itens = []
    for c in ref.get("conceitos") or []:
        nome = f'{e(c["nome"])} · {c["compras"]} compra(s) · {brl_un(c["mediana"])}{un}'
        itens.append(f'<li><a href="{e(ref["app"])}/#/precos/{e(c["id"])}" target="_blank" rel="noopener">{nome}</a></li>'
                     if ref.get("app") else f"<li>{nome}</li>")
    aqui = ""
    cands = [(m, comparar(m, ref, cfg)) for m in melhores if m]
    cands = [(m, c) for m, c in cands if c and c["com_frete"] is not None]
    if cands:
        m, c = min(cands, key=lambda mc: mc[1]["com_frete"])
        aqui = (f'<div>Melhor aqui: <b>{brl_un(c["com_frete"])}{un}</b> entregue ({e(m["loja"])}), '
                f'{1 - c["com_frete"] / ref["mediana"]:.0%} abaixo.</div>')
    return (f'<aside class="aug"><div>No Augustinus você paga <b>{brl_un(ref["mediana"])}{un}</b> '
            f'<span class="det">mediana de {ref["compras"]} compra(s) no último ano</span></div>{aqui}'
            f'<ul>{"".join(itens)}</ul></aside>')


def gerar_relatorio(cfg, erros: list[str], destino=RELATORIO, origem=HISTORICO, publico=False,
                    link_historico="historico.html", referencia=None, botao=""):
    """publico=True é a cópia do GitHub Pages: sem o CEP, com noindex e com volta para o índice."""
    historico = ler_historico(origem)
    descoberta = cfg.get("modo") == "descoberta"
    ultima, res = analisar(historico, cfg)
    e = html.escape
    cards, linhas_tab = [], []
    un = sufixo(cfg) if descoberta else "/L"
    conta = not descoberta or unidade_de_comparacao(cfg) is not None  # há "por litro/unidade" a mostrar
    ordem = sorted(res, key=lambda r: r["melhor"]["valor"] if r["melhor"] else 1e12)
    for r in ordem:
        p, mel = r["prod"], r["melhor"]
        if mel:
            if descoberta:
                n = unidades_na_oferta(mel["produto"], cfg)
                por_un = mel["total_pix"] / n if n else None
            else:
                por_un = mel["total_pix"] / p["litros"] if p.get("litros") else None
            delta = ""
            if r["antes"] is not None:
                d = mel["valor"] - r["antes"]
                if abs(d) >= (0.001 if por_unidade(cfg) else 0.01):
                    cls = "desce" if d < 0 else "sobe"
                    seta = "▼" if d < 0 else "▲"
                    delta = f'<span class="{cls}">{seta} {brl_un(abs(d)) if por_unidade(cfg) else brl(abs(d))}{un if por_unidade(cfg) else ""}</span>'
            eh_min = r["minimo"] and mel["valor"] <= r["minimo"]["valor"]
            selo = '<span class="selo">menor preço já visto</span>' if eh_min and len(r["serie"]) > 1 else ""
            corpo = (f'<div class="total">{brl(mel["total_pix"])} {delta}</div>'
                     f'{selo_augustinus(mel, referencia, cfg)}'
                     f'<div class="det">{brl(mel["preco_pix"])}{"" if descoberta else " no Pix"} + '
                     f'{"frete não informado" if mel["frete"] is None else brl(mel["frete"]) + " de frete"}'
                     f' · {e(mel["loja"])} ({e(mel["vendedor"])}) · {e(mel["prazo"])}</div>'
                     f'<div class="det">Cartão: {brl(mel["total_cartao"])} · '
                     + (f'<b>{brl_un(por_un)}{un}</b> entregue{aviso_kit(mel["produto"], cfg) if descoberta else ""} · '
                        if conta else '')
                     + f'mínimo histórico '
                     f'{brl_un(r["minimo"]["valor"]) if por_unidade(cfg) else brl(r["minimo"]["valor"])}{un if por_unidade(cfg) else ""} em {e(r["minimo"]["data"][:10])}</div>'
                     f'<div class="spark">{sparkline(r["serie"])}</div>'
                     f'<a href="{e(mel["link"])}" target="_blank" rel="noopener">abrir na loja →</a>')
        else:
            corpo = '<div class="det">Sem oferta com entrega para o seu CEP nesta rodada.</div>'
            selo = ""
        meta = (e(mel["produto"]) if mel else "") if descoberta else \
            f'{p.get("litros", "?")} L · {e(p.get("medidas", ""))} · {e(p.get("obs", ""))}'
        cards.append(f'<article class="card"><header><h2>{e(p["modelo"])}</h2>{selo}</header>'
                     f'<div class="meta">{meta}</div>{corpo}</article>')
        for o in r["ofertas"]:
            if descoberta:
                n = unidades_na_oferta(o["produto"], cfg)
                primeira = (f'<td>{e(o["produto"])}</td><td>{e(o["loja"])}</td><td>{e(o["vendedor"])}</td>'
                            + (f'<td class="n">{brl_un(o["total_pix"] / n if n and o["total_pix"] else None)}'
                               f'{aviso_kit(o["produto"], cfg, curto=True)}</td>' if conta else ''))
            else:
                primeira = f'<td>{e(o["modelo"])}</td><td>{e(o["loja"])}</td><td>{e(o["vendedor"])}</td>'
            linhas_tab.append(
                f'<tr>{primeira}'
                f'<td class="n">{brl(o["preco_pix"])}</td><td class="n">{brl(o["frete"])}</td>'
                f'<td class="n"><b>{brl(o["total_pix"])}</b></td><td class="n">{brl(o["total_cartao"])}</td>'
                f'<td>{e(o["prazo"])}</td><td><a href="{e(o["link"])}" target="_blank" rel="noopener">link</a></td></tr>')
    avisos = "".join(f"<li>{e(x)}</li>" for x in erros)
    titulo = cfg.get("titulo")
    cabeca = (f'<th>Produto</th><th>Loja</th><th>Vendedor</th>'
              + (f'<th class="n">Total{un}</th>' if conta else '') + '<th class="n">Preço</th>'
              if descoberta else '<th>Modelo</th><th>Loja</th><th>Vendedor</th><th class="n">Pix</th>')
    colunas = (10 if conta else 9) if descoberta else 9
    rodape = ("Edite o arquivo do monitor em monitores/ para mudar termos e regras; as lojas ficam em lojas.toml."
              if descoberta else "Edite monitores/freezer.toml para mudar modelos; as lojas ficam em lojas.toml.")
    cep = "de casa" if publico else cfg["cep"]
    ordenado = (f"total com frete por unidade ({un})" if por_unidade(cfg)
                else "total com frete" if descoberta else "total no Pix")
    extra_head = '<meta name="robots" content="noindex">' if publico else ""
    volta = '<p class="sub"><a href="index.html">← todos os monitores</a></p>' if publico else ""
    rodape_final = "Coletado numa máquina pessoal; preço e frete para um CEP fixo." if publico else         f"Histórico completo em historico.csv (abre no Excel). {rodape}"
    pagina = f"""<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">{extra_head}<title>{e("Monitor · " + titulo) if titulo else "Monitor de Freezer"}</title>
<style>
{ESTILO}</style></head><body><main>
{volta}<div class="topo"><div><h1>{e(titulo or "Monitor de freezer")}</h1>
<p class="sub">Preço + frete para o CEP {e(cep)} · última consulta {e(ultima or "—")} · ordenado pelo {ordenado} · <a href="{e(link_historico)}">histórico →</a></p>
{f'<p class="atualizar">{botao} <span class="det resposta"></span></p>' if botao else ''}</div>
{quadro_augustinus(referencia, cfg, [r["melhor"] for r in res])}</div>
<section class="grid">{"".join(cards)}</section>
<div class="tab"><table><thead><tr>{cabeca}
<th class="n">Frete</th><th class="n">Total Pix</th><th class="n">Total cartão</th><th>Prazo</th><th></th></tr></thead>
<tbody>{"".join(linhas_tab) or f'<tr><td colspan="{colunas}">Nenhuma oferta encontrada.</td></tr>'}</tbody></table></div>
{f'<h3>Avisos desta rodada</h3><ul class="avisos">{avisos}</ul>' if avisos else ''}
<p class="avisos">{rodape_final}</p>
</main>{ORDENAR}{SCRIPT_ATUALIZAR if botao else ""}</body></html>"""
    destino.parent.mkdir(exist_ok=True)
    destino.write_text(pagina, encoding="utf-8")
    return res


def houve_queda(res) -> bool:
    for r in res:
        if not r["melhor"]:
            continue
        if r["antes"] is None or r["melhor"]["total_pix"] < r["antes"] - 0.01:
            return True
    return False
