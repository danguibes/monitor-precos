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
    assert sorted(a.name for a in site.iterdir()) == ["index.html", "teste-historico.html", "teste.html"]
    assert "R$ 110,00" in (site / "index.html").read_text(encoding="utf-8")
    assert varrer(site, termos_proibidos({"cep": CEP})) == []


def test_indice_tem_novo_monitor_e_editar_quando_ha_repositorio(tmp_path):
    from urllib.parse import parse_qs, urlsplit

    from precos.publicar import gerar_indice, link_editar, link_novo_monitor
    repo = "https://github.com/dono/repo"
    a_mao = {"id": "agua", "nome": "Água", "melhor": None, "ultima": None, "cfg": {"nome": "Água"}}
    gerar_indice([a_mao], tmp_path / "i.html", repo, ["Pedido #3 aberto por @outro foi ignorado"])
    pagina = (tmp_path / "i.html").read_text(encoding="utf-8")
    assert "+ Novo monitor" in pagina and "/edit/main/monitores/agua.toml" in pagina  # escrito à mão: arquivo
    assert "Pedido #3 aberto por @outro foi ignorado" in pagina  # pedido de terceiro aparece na página
    assert link_novo_monitor(repo) == f"{repo}/issues/new?template=novo-monitor.yml"
    # criado pelo formulário: o editar reabre o formulário preenchido
    cfg = {"nome": "Detergente", "pedido": {"termos": "detergente\nlava louça", "pack": "6"}}
    q = parse_qs(urlsplit(link_editar(repo, "detergente", cfg)).query)
    assert q["template"] == ["novo-monitor.yml"] and q["monitor"] == ["detergente"]
    assert q["termos"] == ["detergente\nlava louça"] and q["pack"] == ["6"]
    gerar_indice([a_mao], tmp_path / "sem.html")  # sem repositório, sem botão
    assert "Novo monitor" not in (tmp_path / "sem.html").read_text(encoding="utf-8")


def test_modelo_de_monitor_e_valido_e_nao_fica_em_monitores():
    import tomllib
    from precos.publicar import MODELO
    m = tomllib.loads(MODELO.read_text(encoding="utf-8"))
    assert m["modo"] == "descoberta" and m["termos"] and "lojas" not in m
    assert MODELO.parent.name != "monitores"  # senão viraria um monitor de verdade


def test_serie_do_card_segue_o_numero_grande_do_card():
    from precos.publicar import serie_do_card
    l = lambda data, total, frete=0.0, produto="Agua com gas 1,5 L": {
        "data": data, "total_pix": total, "frete": frete, "produto": produto}
    linhas = [l("2026-11-01 06:00", 30.0), l("2026-11-01 18:00", 24.0), l("2026-11-02 06:00", 99.0, None),
              l("2026-11-02 06:00", 27.0)]
    assert serie_do_card(linhas, {}) == [24.0, 27.0]  # sem unidade: o total, o menor do dia, com frete
    por_litro = {"modo": "descoberta", "regras": {"volume_ml": [1400, 1600]}}
    assert serie_do_card(linhas, por_litro) == [16.0, 18.0]  # 1,5 L: o mesmo número, por litro
