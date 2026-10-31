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
    assert "▼ R$ 100,00" in html and "R$ 9,00/L" in html


def test_descarte_das_linhas_dos_defeitos_corrigidos(tmp_path):
    from precos.historico import descartar
    arq = tmp_path / "h.csv"
    gravar_historico([
        oferta("Magalu", "M", "P", "V", 1525.26, 1449.0, 1525.26, "", "x", "2026-10-30 17:38"),  # frete = preço
        oferta("Atacadão", "M", "P", "V", 19.74, None, 0.0, "", "x", "2026-10-31 12:56"),       # antes da correção
        oferta("Atacadão", "M", "P", "V", 21.00, None, 0.0, "", "x", "2026-10-31 13:02"),       # depois: vale
        oferta("Mambo", "M", "P", "V", 30.0, None, 12.9, "", "x", "2026-10-30 18:00"),           # vale
    ], arq)
    assert len(ler_historico(arq, bruto=True)) == 4
    boas = ler_historico(arq)
    assert [(l["loja"], l["data"]) for l in boas] == [("Atacadão", "2026-10-31 13:02"), ("Mambo", "2026-10-30 18:00")]
    _, contagem = descartar(ler_historico(arq, bruto=True))
    assert sorted(contagem.values()) == [1, 1]
