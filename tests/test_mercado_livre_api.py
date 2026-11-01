"""Mercado Livre pela API: catálogo, anúncios novos mais baratos, frete mais barato e o retorno ao navegador.

As respostas imitam as reais de 01/11/2026 (campos e formato), montadas à mão: a de
frete real repete o CEP e o endereço de destino, e o repositório é público.
"""
import pytest

from precos import coleta
from precos.lojas import mercado_livre_api as ml
from precos.pedidos import preservar

CATALOGO = {"results": [
    {"id": "MLB1", "name": "Colchão Casal Guldi Comfort Mola Ensacada"},
    {"id": "MLB2", "name": "Colchão Casal Supreme D33 Gazin"},          # outra marca: o filtro tira
    {"id": "MLB3", "name": "Colchão Casal Guldi Dream (sem anúncio)"},  # 404 No winners found
]}
ANUNCIOS = {"results": [
    {"item_id": "MLB900", "price": 1999.0, "condition": "new", "currency_id": "BRL", "seller_id": 7},
    {"item_id": "MLB901", "price": 1820.45, "condition": "new", "currency_id": "BRL", "seller_id": 8},
    {"item_id": "MLB902", "price": 900.0, "condition": "used", "currency_id": "BRL", "seller_id": 9},  # usado: fora
    {"item_id": "MLB903", "price": 2500.0, "condition": "new", "currency_id": "BRL", "seller_id": 7},  # 3º novo: fora
]}
FRETE = {"options": [
    {"name": "Normal", "cost": 105.71, "estimated_delivery_time": {"date": "2026-11-12T00:00:00-03:00"}},
    {"name": "Expresso", "cost": 149.9, "estimated_delivery_time": {"date": "2026-11-05T00:00:00-03:00"}},
]}


def falso(rotas, chamadas):
    def _pedir(caminho, token=None, form=None):
        chamadas.append((caminho.split("?")[0], token))
        for prefixo, resposta in rotas.items():
            if caminho.startswith(prefixo):
                return resposta
        return 404, None
    return _pedir


def rotas_ok():
    return {"/oauth/token": (200, {"access_token": "tok"}),
            "/products/search": (200, CATALOGO),
            "/products/MLB1/items": (200, ANUNCIOS),
            "/products/MLB3/items": (404, None),
            "/users/7": (200, {"nickname": "LOJA SETE"}), "/users/8": (200, {"nickname": "MOBLY"}),
            "/items/MLB901/shipping_options": (200, FRETE),
            "/items/MLB900/shipping_options": (200, {"options": []})}


GULDI = lambda titulo, prod: "guldi" in titulo.lower()
CFG = {"cep": "01310-100"}
PRODS = [{"modelo": "Colchão Guldi", "busca": "colchao guldi casal"}]


def test_anuncios_novos_mais_baratos_com_o_frete_mais_barato(monkeypatch):
    chamadas = []
    monkeypatch.setattr(ml, "_pedir", falso(rotas_ok(), chamadas))
    erros = []
    ofs = ml.coletar(CFG, PRODS, "2026-11-01 10:00", GULDI, erros, ml={"client_id": "x", "client_secret": "y"})
    assert [o["sku"] for o in ofs] == ["MLB901", "MLB900"]          # os 2 novos mais baratos; usado fora; Gazin fora
    o = ofs[0]
    assert o["preco"] == 1820.45 and o["frete"] == 105.71 and o["total_pix"] == 1926.16
    assert o["vendedor"] == "MOBLY" and o["prazo"] == "até 12/11" and o["loja"] == "Mercado Livre"
    assert o["link"] == "https://produto.mercadolivre.com.br/MLB-901"
    assert ofs[1]["frete"] is None and "1 anúncio(s) sem frete" in erros[0]
    # o frete vai SEM token (com ele dá 403); o catálogo e os anúncios vão COM
    assert ("/items/MLB901/shipping_options", None) in chamadas
    assert ("/products/MLB1/items", "tok") in chamadas


def test_sem_credenciais_ou_token_recusado_levanta_sem_acesso(monkeypatch):
    with pytest.raises(ml.SemAcesso):
        ml.pedir_token(None)
    monkeypatch.setattr(ml, "_pedir", falso({"/oauth/token": (400, None)}, []))
    with pytest.raises(ml.SemAcesso):
        ml.pedir_token({"client_id": "x", "client_secret": "y"})


def test_catalogo_recusado_volta_para_o_navegador(monkeypatch):
    rotas = dict(rotas_ok(), **{"/products/search": (403, None)})
    monkeypatch.setattr(ml, "_pedir", falso(rotas, []))
    with pytest.raises(ml.SemAcesso):
        ml.coletar(CFG, PRODS, "d", GULDI, [], ml={"client_id": "x", "client_secret": "y"})


def test_coleta_tira_o_ml_do_navegador_so_quando_a_api_responde(monkeypatch):
    vistos = {}
    monkeypatch.setattr(coleta, "coletar_navegador",
                        lambda cfg, *a: (vistos.setdefault("lojas", cfg["lojas_navegador"]), ([], []))[1])
    monkeypatch.setattr(coleta.mercado_livre_api, "coletar", lambda *a, **k: [])
    cfg = {"modo": "descoberta", "titulo": "x", "termos": ["x"], "regras": {}, "cep": "01310-100",
           "lojas_navegador": ["Magalu", "Mercado Livre"], "mercado_livre": "api"}
    coleta.coletar_tudo(cfg, {}, lambda m: None)
    assert vistos["lojas"] == ["Magalu"]

    def recusa(*a, **k):
        raise coleta.mercado_livre_api.SemAcesso("token do app recusado (HTTP 400)")
    monkeypatch.setattr(coleta.mercado_livre_api, "coletar", recusa)
    vistos.clear()
    _, erros = coleta.coletar_tudo(cfg, {}, lambda m: None)
    assert vistos["lojas"] == ["Magalu", "Mercado Livre"] and "pelo navegador" in erros[0]
    vistos.clear()
    coleta.coletar_tudo(dict(cfg, mercado_livre=None), {}, lambda m: None)   # sem a chave: navegador
    assert vistos["lojas"] == ["Magalu", "Mercado Livre"]
    monkeypatch.setattr(coleta.mercado_livre_api, "coletar", lambda *a, **k: [])
    vistos.clear()
    coleta.coletar_tudo(dict(cfg, mercado_livre="ambos"), {}, lambda m: None)  # ambos: API e navegador
    assert vistos["lojas"] == ["Magalu", "Mercado Livre"]


def test_frete_e_link():
    assert ml.ler_frete(FRETE) == (105.71, "até 12/11")
    assert ml.ler_frete({"options": [{"cost": 0, "estimated_delivery_time": {"date": "2026-11-04T00:00:00-03:00"}},
                                     {"cost": 0, "estimated_delivery_time": {"date": "2026-11-02T00:00:00-03:00"}}]}) \
        == (0.0, "até 02/11")                                   # grátis empatado: o que chega antes
    assert ml.ler_frete({}) == (None, "") and ml.link_do_anuncio("lixo") == ""


def test_editar_pelo_formulario_preserva_api_e_pausa():
    antigo = 'nome = "x"\npausado = true\nmercado_livre = "api"\n\n[regras]\nincluir = []\n'
    novo = 'nome = "x"\nmodo = "descoberta"\n\n[regras]\nincluir = ["a"]\n'
    import tomllib
    cfg = tomllib.loads(preservar(novo, antigo))
    assert cfg["pausado"] is True and cfg["mercado_livre"] == "api" and cfg["regras"]["incluir"] == ["a"]
    assert preservar(novo, 'nome = "x"\n') == novo
