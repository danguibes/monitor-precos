"""Página de histórico: séries por grupo, melhor por rodada, descartes à vista e sem CEP no público."""
from precos.base import oferta
from precos.historico import gravar_historico
from precos.historico_pagina import gerar_historico, melhor_por_rodada, series
from precos.historico import ler_historico

CFG = {"cep": "12345-678", "nome": "Água", "titulo": "Água teste", "modo": "descoberta"}


def _hist(tmp_path):
    arq = tmp_path / "h.csv"
    def of(loja, total, data, frete=0.0):
        o = oferta(loja, loja, "P " + loja, "", total, None, frete, "", "x", data)
        return o
    gravar_historico([
        of("A", 30.0, "2026-10-30 10:00"), of("B", 28.0, "2026-10-30 10:00"),
        of("A", 25.0, "2026-10-31 10:00"), of("B", 29.0, "2026-10-31 10:00"),
        of("C", 20.0, "2026-10-31 10:00", frete=None),                    # sem frete: não entra
        of("Atacadão", 10.0, "2026-10-30 12:00"),                          # descartada pela regra
    ], arq)
    return arq


def test_series_e_melhor_por_rodada(tmp_path):
    s = series(ler_historico(_hist(tmp_path)))
    assert set(s) == {"A", "B"}  # C sem frete fica fora; Atacadão antes da correção, descartado
    m = melhor_por_rodada(s)
    assert m["2026-10-30 10:00"]["loja"] == "B" and m["2026-10-31 10:00"]["loja"] == "A"


def test_pagina_publica_tem_graficos_tabelas_e_descartes_sem_cep(tmp_path):
    destino = tmp_path / "x-historico.html"
    gerar_historico(CFG, destino, _hist(tmp_path), volta="x.html", publico=True)
    p = destino.read_text(encoding="utf-8")
    assert "12345-678" not in p and "CEP de casa" in p and 'content="noindex"' in p
    assert p.count("<svg") == 2 and 'href="x.html"' in p
    assert "R$ 25,00" in p and "1 linha(s): Atacadão consultado pelo vendedor genérico" in p
    assert 'data-dica="31/10 10:00 · A · R$ 25,00 com frete"' in p


def test_pagina_sem_dados_nao_quebra(tmp_path):
    destino = tmp_path / "h.html"
    gerar_historico(CFG, destino, tmp_path / "nao-existe.csv", volta="r.html")
    assert "Ainda sem rodadas" in destino.read_text(encoding="utf-8")


def test_passo_redondo_no_eixo():
    from precos.historico_pagina import passo_redondo
    assert [passo_redondo(v) for v in (0.85, 2.2, 3.0, 7.0, 180.0)] == [1.0, 2.5, 5.0, 10.0, 200.0]
