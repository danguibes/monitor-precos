"""Relatório HTML: um card por modelo e a tabela de todas as ofertas da última rodada."""
from __future__ import annotations

import html

from .base import HISTORICO, RELATORIO, brl
from .historico import ler_historico
from .unidades import litros as litros_do_titulo
from .unidades import volume_ml


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
.selo-aug{display:inline-block;background:var(--ok);color:var(--card);border-radius:99px;font-size:12px;font-weight:600;padding:3px 10px;margin:6px 0 2px;text-decoration:none}
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


def litros_oferta(produto: str, pack: int | None):
    """Com pack montado, o volume total é pack × o volume de uma unidade."""
    if pack:
        v = volume_ml(produto)
        return pack * v / 1000 if v else None
    return litros_do_titulo(produto)


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


def analisar(historico, cfg):
    """Para cada modelo: melhor oferta da última rodada, da anterior e mínimo histórico."""
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
        linhas = [l for l in historico if l["modelo"] == m and l["total_pix"] is not None]
        atual = [l for l in linhas if l["data"] == ultima]
        antes = [l for l in linhas if l["data"] == anterior]
        # ofertas sem frete informado (Shopee, às vezes ML) não "ganham" o ranking
        com_frete = lambda ls: [l for l in ls if l.get("frete") is not None]
        atual_cf, antes_cf, linhas_cf = com_frete(atual), com_frete(antes), com_frete(linhas)
        melhor = min(atual_cf or atual, key=lambda l: l["total_pix"]) if atual else None
        melhor_antes = min((l["total_pix"] for l in (antes_cf or antes)), default=None)
        minimo = min(linhas_cf or linhas, key=lambda l: l["total_pix"]) if linhas else None
        por_dia = {}
        for l in linhas_cf or linhas:
            d = l["data"][:10]
            por_dia[d] = min(por_dia.get(d, 1e12), l["total_pix"])
        serie = [por_dia[d] for d in sorted(por_dia)]
        res.append({"prod": prod, "melhor": melhor, "antes": melhor_antes,
                    "minimo": minimo, "serie": serie, "ofertas": sorted(atual, key=lambda l: l["total_pix"])})
    return ultima, res


def html_augustinus(oferta, ref, cfg) -> str:
    """Selo "abaixo do que você paga", com a conta e o link para o histórico do item no Augustinus."""
    from .augustinus import comparar
    cmp = comparar(oferta, ref, cfg)
    if not cmp:
        return ""
    e = html.escape
    un = "/L" if ref["unidade"] == "litro" else "/" + cfg.get("unidade_nome", "un.")
    pago = f'você paga {brl(cmp["mediana"])}{un} (mediana de {ref["compras"]} compra(s) no Augustinus)'
    link = f'{ref["app"]}/#/precos/{ref["conceito_id"]}' if ref.get("app") and ref.get("conceito_id") else ""
    abre = f'<a class="selo-aug" href="{e(link)}" target="_blank" rel="noopener">' if link else '<span class="selo-aug">'
    fecha = "</a>" if link else "</span>"
    if cmp["nivel"] == "forte":
        return (f'<div>{abre}▼ abaixo do que você paga{fecha}</div>'
                f'<div class="det">{brl(cmp["com_frete"])}{un} entregue · {e(pago)}</div>')
    return (f'<div class="det">O produto sai {brl(cmp["so_produto"])}{un}, abaixo dos {brl(cmp["mediana"])}{un} '
            f'que você paga, mas o frete come a diferença'
            + (f' · <a href="{e(link)}" target="_blank" rel="noopener">ver no Augustinus</a>' if link else "")
            + '.</div>')


def gerar_relatorio(cfg, erros: list[str], destino=RELATORIO, origem=HISTORICO, publico=False,
                    link_historico="historico.html", referencia=None):
    """publico=True é a cópia do GitHub Pages: sem o CEP, com noindex e com volta para o índice."""
    historico = ler_historico(origem)
    descoberta = cfg.get("modo") == "descoberta"
    pack = (cfg.get("regras") or {}).get("montar_pack")
    ultima, res = analisar(historico, cfg)
    e = html.escape
    cards, linhas_tab = [], []
    ordem = sorted(res, key=lambda r: r["melhor"]["total_pix"] if r["melhor"] else 1e12)
    for r in ordem:
        p, mel = r["prod"], r["melhor"]
        if mel:
            lt = litros_oferta(mel["produto"], pack) if descoberta else p.get("litros")
            litro = mel["total_pix"] / lt if lt else None
            delta = ""
            if r["antes"] is not None:
                d = mel["total_pix"] - r["antes"]
                if abs(d) >= 0.01:
                    cls = "desce" if d < 0 else "sobe"
                    seta = "▼" if d < 0 else "▲"
                    delta = f'<span class="{cls}">{seta} {brl(abs(d))}</span>'
            eh_min = r["minimo"] and mel["total_pix"] <= r["minimo"]["total_pix"]
            selo = '<span class="selo">menor preço já visto</span>' if eh_min and len(r["serie"]) > 1 else ""
            corpo = (f'<div class="total">{brl(mel["total_pix"])} {delta}</div>'
                     f'{html_augustinus(mel, referencia, cfg)}'
                     f'<div class="det">{brl(mel["preco_pix"])}{"" if descoberta else " no Pix"} + '
                     f'{"frete não informado" if mel["frete"] is None else brl(mel["frete"]) + " de frete"}'
                     f' · {e(mel["loja"])} ({e(mel["vendedor"])}) · {e(mel["prazo"])}</div>'
                     f'<div class="det">Cartão: {brl(mel["total_cartao"])} · '
                     f'{brl(litro)}/litro · mínimo histórico {brl(r["minimo"]["total_pix"])} '
                     f'em {e(r["minimo"]["data"][:10])}</div>'
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
                lt = litros_oferta(o["produto"], pack)
                primeira = (f'<td>{e(o["produto"])}</td><td>{e(o["loja"])}</td><td>{e(o["vendedor"])}</td>'
                            f'<td class="n">{brl(o["total_pix"] / lt if lt and o["total_pix"] else None)}</td>')
            else:
                primeira = f'<td>{e(o["modelo"])}</td><td>{e(o["loja"])}</td><td>{e(o["vendedor"])}</td>'
            linhas_tab.append(
                f'<tr>{primeira}'
                f'<td class="n">{brl(o["preco_pix"])}</td><td class="n">{brl(o["frete"])}</td>'
                f'<td class="n"><b>{brl(o["total_pix"])}</b></td><td class="n">{brl(o["total_cartao"])}</td>'
                f'<td>{e(o["prazo"])}</td><td><a href="{e(o["link"])}" target="_blank" rel="noopener">link</a></td></tr>')
    avisos = "".join(f"<li>{e(x)}</li>" for x in erros)
    titulo = cfg.get("titulo")
    cabeca = ('<th>Produto</th><th>Loja</th><th>Vendedor</th><th class="n">Total/litro</th><th class="n">Preço</th>'
              if descoberta else '<th>Modelo</th><th>Loja</th><th>Vendedor</th><th class="n">Pix</th>')
    colunas = 10 if descoberta else 9
    rodape = ("Edite o arquivo do monitor em monitores/ para mudar termos e regras; as lojas ficam em lojas.toml."
              if descoberta else "Edite monitores/freezer.toml para mudar modelos; as lojas ficam em lojas.toml.")
    cep = "de casa" if publico else cfg["cep"]
    extra_head = '<meta name="robots" content="noindex">' if publico else ""
    volta = '<p class="sub"><a href="index.html">← todos os monitores</a></p>' if publico else ""
    rodape_final = "Coletado numa máquina pessoal; preço e frete para um CEP fixo." if publico else         f"Histórico completo em historico.csv (abre no Excel). {rodape}"
    pagina = f"""<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">{extra_head}<title>{e("Monitor · " + titulo) if titulo else "Monitor de Freezer"}</title>
<style>
{ESTILO}</style></head><body><main>
{volta}<h1>{e(titulo or "Monitor de freezer")}</h1>
<p class="sub">Preço + frete para o CEP {e(cep)} · última consulta {e(ultima or "—")} · ordenado pelo total {"com frete" if descoberta else "no Pix"} · <a href="{e(link_historico)}">histórico →</a></p>
<section class="grid">{"".join(cards)}</section>
<div class="tab"><table><thead><tr>{cabeca}
<th class="n">Frete</th><th class="n">Total Pix</th><th class="n">Total cartão</th><th>Prazo</th><th></th></tr></thead>
<tbody>{"".join(linhas_tab) or f'<tr><td colspan="{colunas}">Nenhuma oferta encontrada.</td></tr>'}</tbody></table></div>
{f'<h3>Avisos desta rodada</h3><ul class="avisos">{avisos}</ul>' if avisos else ''}
<p class="avisos">{rodape_final}</p>
</main>{ORDENAR}</body></html>"""
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
