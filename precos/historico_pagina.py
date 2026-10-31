"""Página de histórico de um monitor: dois gráficos e duas tabelas, HTML estático.

Agrupa por "modelo" — que no modo descoberta é a loja (um card por loja) e no
acompanhado é o modelo do freezer. Só contam ofertas com frete conhecido, como
no card de melhor oferta. As linhas de defeitos corrigidos saem pela regra de
historico.DESCARTES, e a página diz quantas e por quê.

Gráficos em SVG à mão, sem biblioteca: uma escala, linhas de 2px, pontos de 8px
com área de toque maior, dica ao passar o mouse, e no máximo três séries (as três
primeiras cores da paleta, validadas juntas nos dois modos).
"""
from __future__ import annotations

import html
import math
from datetime import datetime

from .base import brl
from .historico import descartar, ler_historico
from .relatorio import ESTILO

LARG, ALT = 760, 260
MARGEM = {"esq": 78, "dir": 120, "cima": 16, "baixo": 34}
CORES = """
.serie-1{--cor:#2a78d6}.serie-2{--cor:#eb6834}.serie-3{--cor:#1baf7a}
@media (prefers-color-scheme:dark){.serie-1{--cor:#3987e5}.serie-2{--cor:#d95926}.serie-3{--cor:#199e70}}
.grafico{background:var(--card);border:1px solid var(--ln);border-radius:12px;padding:12px 14px;margin:14px 0;position:relative}
.grafico h2{margin:0 0 6px}
.grafico svg{width:100%;height:auto;display:block}
.grafico .linha{fill:none;stroke:var(--cor);stroke-width:2;stroke-linejoin:round;stroke-linecap:round}
.grafico .ponto{fill:var(--cor);stroke:var(--card);stroke-width:2}
.grafico .toque{fill:transparent;cursor:pointer}
.grafico .grade{stroke:var(--ln);stroke-width:1}
.grafico .eixo{fill:var(--mut);font-size:12px}
.grafico .rotulo{fill:var(--tx);font-size:12px}
.legenda{display:flex;gap:16px;flex-wrap:wrap;font-size:13px;color:var(--tx);margin:2px 0 4px}
.legenda span::before{content:"";display:inline-block;width:14px;height:3px;border-radius:2px;background:var(--cor);vertical-align:middle;margin-right:6px}
.dica{position:absolute;pointer-events:none;background:var(--card);border:1px solid var(--ln);border-radius:8px;padding:6px 8px;font-size:12px;color:var(--tx);box-shadow:0 2px 8px rgba(0,0,0,.12);display:none;white-space:nowrap}
"""
DICA = """<script>
document.querySelectorAll(".grafico").forEach(g => {
  const d = g.querySelector(".dica");
  g.querySelectorAll(".toque").forEach(t => {
    t.addEventListener("mouseenter", () => {
      d.textContent = t.dataset.dica; d.style.display = "block";
      const r = g.getBoundingClientRect(), p = t.getBoundingClientRect();
      d.style.left = Math.min(p.left - r.left + 12, r.width - d.offsetWidth - 8) + "px";
      d.style.top = (p.top - r.top - 34) + "px";
    });
    t.addEventListener("mouseleave", () => { d.style.display = "none"; });
  });
});
</script>"""


def passo_redondo(bruto: float) -> float:
    """O menor passo 1, 2, 2,5 ou 5 × 10^k que cobre `bruto`."""
    if bruto <= 0:
        return 1.0
    base = 10 ** math.floor(math.log10(bruto))
    return next(m * base for m in (1, 2, 2.5, 5, 10) if m * base >= bruto)


def _rodadas(linhas):
    return sorted({l["data"] for l in linhas})


def series(linhas):
    """{grupo: {rodada: linha mais barata}} — só ofertas com frete conhecido."""
    s = {}
    for l in linhas:
        if l["frete"] is None or l["total_pix"] is None:
            continue
        g = s.setdefault(l["modelo"], {})
        if l["data"] not in g or l["total_pix"] < g[l["data"]]["total_pix"]:
            g[l["data"]] = l
    return s


def melhor_por_rodada(s):
    """{rodada: linha mais barata de todas}."""
    m = {}
    for g in s.values():
        for r, l in g.items():
            if r not in m or l["total_pix"] < m[r]["total_pix"]:
                m[r] = l
    return m


def _svg(series_pts, rodadas, rotulos):
    """series_pts: [(classe, nome, {rodada: linha})]. Uma escala de y, x pelo tempo."""
    e = html.escape
    t = {r: datetime.strptime(r, "%Y-%m-%d %H:%M").timestamp() for r in rodadas}
    vals = [l["total_pix"] for _, _, pts in series_pts for l in pts.values()]
    if not vals:
        return "<p class='det'>Ainda sem rodadas com frete conhecido.</p>"
    lo, hi = min(vals), max(vals)
    folga = (hi - lo) * 0.08 or hi * 0.05 or 1
    lo, hi = max(0, lo - folga), hi + folga
    passo_y = passo_redondo((hi - lo) / 4)  # marcas em R$ 1, 2, 5, 10… e não em R$ 30,22
    lo, hi = math.floor(lo / passo_y) * passo_y, math.ceil(hi / passo_y) * passo_y
    t0, t1 = min(t.values()), max(t.values())
    w = LARG - MARGEM["esq"] - MARGEM["dir"]
    h = ALT - MARGEM["cima"] - MARGEM["baixo"]
    x = lambda r: MARGEM["esq"] + (w * (t[r] - t0) / (t1 - t0) if t1 > t0 else w / 2)
    y = lambda v: MARGEM["cima"] + h * (1 - (v - lo) / (hi - lo))
    partes = []
    for k in range(round((hi - lo) / passo_y) + 1):  # grade e eixo y, recessivos
        v = lo + k * passo_y
        partes.append(f'<line class="grade" x1="{MARGEM["esq"]}" x2="{LARG - MARGEM["dir"]}" y1="{y(v):.1f}" y2="{y(v):.1f}"/>'
                      f'<text class="eixo" x="{MARGEM["esq"] - 8}" y="{y(v) + 4:.1f}" text-anchor="end">{e(brl(v))}</text>')
    dias = sorted({r[:10] for r in rodadas})
    passo = max(1, len(dias) // 6)
    for d in dias[::passo]:  # um rótulo por dia, na primeira rodada do dia
        r = min(r for r in rodadas if r.startswith(d))
        partes.append(f'<text class="eixo" x="{x(r):.1f}" y="{ALT - 10}" text-anchor="middle">{d[8:10]}/{d[5:7]}</text>')
    for classe, nome, pts in series_pts:
        rs = sorted(pts)
        if not rs:
            continue
        caminho = " ".join(f"{'M' if i == 0 else 'L'}{x(r):.1f},{y(pts[r]['total_pix']):.1f}" for i, r in enumerate(rs))
        partes.append(f'<g class="{classe}"><path class="linha" d="{caminho}"/>')
        for r in rs:
            l = pts[r]
            dica = f"{r[8:10]}/{r[5:7]} {r[11:]} · {l['loja']} · {brl(l['total_pix'])} com frete"
            partes.append(f'<circle class="ponto" cx="{x(r):.1f}" cy="{y(l["total_pix"]):.1f}" r="4"/>'
                          f'<circle class="toque" cx="{x(r):.1f}" cy="{y(l["total_pix"]):.1f}" r="11" data-dica="{e(dica)}"/>')
        if rotulos:  # rótulo direto no fim da linha
            ult = rs[-1]
            partes.append(f'<text class="rotulo" x="{x(ult) + 10:.1f}" y="{y(pts[ult]["total_pix"]) + 4:.1f}">{e(nome[:16])}</text>')
        partes.append("</g>")
    return (f'<svg viewBox="0 0 {LARG} {ALT}" role="img" aria-label="preço com frete ao longo das rodadas">'
            + "".join(partes) + "</svg>")


def gerar_historico(cfg, destino, origem, volta: str, publico=False) -> None:
    e = html.escape
    descoberta = cfg.get("modo") == "descoberta"
    grupo = "Loja" if descoberta else "Modelo"
    boas, descartes = descartar(ler_historico(origem, bruto=True))
    s = series(boas)
    rodadas = _rodadas([l for g in s.values() for l in g.values()])
    melhor = melhor_por_rodada(s)

    graf1 = _svg([("serie-1", "Melhor", melhor)], rodadas, rotulos=False)
    ultima = rodadas[-1] if rodadas else None
    top = sorted((g for g in s if ultima in s[g]), key=lambda g: s[g][ultima]["total_pix"])[:3]
    series_top = [(f"serie-{i + 1}", g, s[g]) for i, g in enumerate(top)]
    graf2 = _svg(series_top, rodadas, rotulos=True)
    legenda = "".join(f'<span class="serie-{i + 1}">{e(g)}</span>' for i, g in enumerate(top))

    por_dia = {}
    for r, l in melhor.items():
        d = r[:10]
        if d not in por_dia or l["total_pix"] < por_dia[d]["total_pix"]:
            por_dia[d] = l
    linhas_dia = "".join(
        f'<tr><td>{d[8:10]}/{d[5:7]}/{d[:4]}</td><td class="n"><b>{brl(l["total_pix"])}</b></td>'
        f'<td>{e(l["loja"])}</td><td>{e(l["produto"][:70])}</td></tr>' for d, l in sorted(por_dia.items(), reverse=True))
    linhas_grupo = []
    for g, pts in sorted(s.items(), key=lambda kv: min(l["total_pix"] for l in kv[1].values())):
        minimo = min(pts.values(), key=lambda l: l["total_pix"])
        agora = pts.get(ultima)
        linhas_grupo.append(
            f'<tr><td>{e(g)}</td><td class="n">{brl(agora["total_pix"]) if agora else "—"}</td>'
            f'<td class="n">{brl(minimo["total_pix"])}</td><td>{minimo["data"][8:10]}/{minimo["data"][5:7]}</td>'
            f'<td class="n">{len(pts)}</td></tr>')
    nota = "".join(f"<li>{n} linha(s): {e(m)}</li>" for m, n in descartes.items())
    titulo = cfg.get("titulo") or cfg.get("nome", "")
    cep = "de casa" if publico else cfg.get("cep", "")

    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(f"""<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">{'<meta name="robots" content="noindex">' if publico else ''}
<title>{e("Histórico · " + titulo)}</title><style>{ESTILO}{CORES}</style></head><body><main>
<p class="sub"><a href="{e(volta)}">← ofertas de agora</a></p>
<h1>{e("Histórico · " + titulo)}</h1>
<p class="sub">{len(rodadas)} rodada(s) com frete conhecido{f" desde {rodadas[0][8:10]}/{rodadas[0][5:7]}" if rodadas else ""} · preço + frete para o CEP {e(cep)} · total no Pix</p>
<section class="grafico"><h2>Melhor oferta com frete, rodada a rodada</h2>{graf1}<div class="dica"></div></section>
<section class="grafico"><h2>As 3 mais baratas na última rodada</h2><div class="legenda">{legenda}</div>{graf2}<div class="dica"></div></section>
<div class="tab"><h2>Melhor de cada dia</h2><table><thead><tr><th>Dia</th><th class="n">Total</th><th>Loja</th><th>Produto</th></tr></thead>
<tbody>{linhas_dia or '<tr><td colspan="4">Sem dados ainda.</td></tr>'}</tbody></table></div>
<div class="tab"><h2>Por {grupo.lower()}</h2><table><thead><tr><th>{grupo}</th><th class="n">Última rodada</th><th class="n">Mínimo</th><th>Quando</th><th class="n">Rodadas</th></tr></thead>
<tbody>{"".join(linhas_grupo) or '<tr><td colspan="5">Sem dados ainda.</td></tr>'}</tbody></table></div>
{f'<h3>Linhas descartadas</h3><ul class="avisos">{nota}</ul><p class="avisos">Elas continuam no CSV; só não entram nas contas.</p>' if nota else ''}
</main>{DICA}</body></html>""", encoding="utf-8")
