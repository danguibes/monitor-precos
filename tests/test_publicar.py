"""Publicação no GitHub Pages: a página pública não leva o CEP, e a varredura barra se levar."""
from precos.base import oferta
from precos.historico import gravar_historico
from precos.publicar import gerar_site, termos_proibidos, varrer
from precos.relatorio import gerar_relatorio

CEP = "12345-678"
CFG = {"cep": CEP, "nome": "Teste", "produtos": [{"modelo": "M1", "litros": 100}]}


def test_termos_proibidos_inclui_cep_com_e_sem_traco_e_a_lista_local():
    t = termos_proibidos({"cep": CEP, "nao_publicar": ["Rua das Flores"]})
    assert set(t) == {CEP, "12345678", "Rua das Flores"}


def test_varredura_acha_o_cep_em_qualquer_formato(tmp_path):
    (tmp_path / "a.html").write_text("frete para 12345678", encoding="utf-8")
    (tmp_path / "b.html").write_text("nada aqui", encoding="utf-8")
    assert varrer(tmp_path, termos_proibidos({"cep": CEP})) == ["a.html: 12345678"]


def test_relatorio_publico_nao_tem_o_cep_e_tem_noindex(tmp_path):
    hist = tmp_path / "h.csv"
    gravar_historico([oferta("Loja", "M1", "P", "V", 100.0, None, 10.0, "", "x", "2026-10-30 10:00")], hist)
    gerar_relatorio(CFG, [], tmp_path / "privado.html", hist)
    gerar_relatorio(CFG, [], tmp_path / "publico.html", hist, publico=True)
    privado = (tmp_path / "privado.html").read_text(encoding="utf-8")
    publico = (tmp_path / "publico.html").read_text(encoding="utf-8")
    assert CEP in privado  # o local mostra o CEP: é para você
    assert CEP not in publico and "CEP de casa" in publico
    assert 'name="robots" content="noindex"' in publico and 'href="index.html"' in publico


def test_site_tem_indice_e_um_relatorio_por_monitor_sem_cep(tmp_path):
    hist = tmp_path / "h.csv"
    gravar_historico([oferta("Loja", "M1", "P", "V", 100.0, None, 10.0, "", "x", "2026-10-30 10:00")], hist)
    monitores = [{"id": "teste", "cfg": CFG, "historico": hist, "estado": tmp_path / "estado.json"}]
    site = tmp_path / "site"
    gerar_site(monitores, site)
    assert sorted(a.name for a in site.iterdir()) == ["index.html", "teste.html"]
    assert "R$ 110,00" in (site / "index.html").read_text(encoding="utf-8")
    assert varrer(site, termos_proibidos({"cep": CEP})) == []
