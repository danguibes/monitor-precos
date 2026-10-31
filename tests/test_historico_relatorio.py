"""Histórico em CSV e relatório gerado a partir dele."""
from precos.base import oferta
from precos.historico import gravar_historico, ler_historico
from precos.relatorio import gerar_relatorio, houve_queda

CFG = {"cep": "00000-000", "produtos": [{"modelo": "M1", "litros": 100}]}


def test_historico_ida_e_volta(tmp_path):
    arq = tmp_path / "h.csv"
    gravar_historico([oferta("Loja", "M1", "P", "V", 1000.0, 950.0, 49.9, "2 dias", "x", "2026-10-30 10:00")], arq)
    (linha,) = ler_historico(arq)
    assert linha["total_pix"] == 999.9
    assert "999,90" in arq.read_text(encoding="utf-8-sig")


def test_relatorio_mostra_queda(tmp_path):
    arq = tmp_path / "h.csv"
    gravar_historico([oferta("A", "M1", "P", "V", 1000.0, None, 0.0, "", "x", "2026-10-29 10:00")], arq)
    gravar_historico([oferta("A", "M1", "P", "V", 900.0, None, 0.0, "", "x", "2026-10-30 10:00")], arq)
    destino = tmp_path / "r.html"
    res = gerar_relatorio(CFG, [], destino, arq)
    assert houve_queda(res)
    html = destino.read_text(encoding="utf-8")
    assert "▼ R$ 100,00" in html and "R$ 9,00/litro" in html
