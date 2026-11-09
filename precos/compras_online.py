"""Os pedidos do Mercado Livre, entregues como vieram à pousada do Augustinus.

O monitor só captura: quem interpreta, classifica e decide o que é compra da casa é
o Augustinus (migration 20260812000101 de lá). O que é da casa volta pela view
monitor.compras_da_casa, como os cupons. O papel monitor_pedidos só tem INSERT em
recebido.pedidos_online: esta porta não lê nada de volta, e por isso o insert é
`on conflict do nothing` SEM alvo (com alvo, exige SELECT).

Medido em 04/11/2026 em 4 transações, e é aqui que se erra calado:

  * A chave do pedido é o número do CAMINHO do link, igual ao "#" do detalhe: é a
    transação, o nível do frete e do total. Uma compra teve 4 orderId em 3 packId
    com um frete só. O item é o orderId.
  * O valor do item vem da LISTA, sempre líquido. O detalhe muda o preço conforme o
    link por onde se entra (a mesma peça a 134,90 pelo próprio link, 78,90 pelos
    outros) e traz uma linha de desconto que às vezes já está no preço.
  * Mas o CUPOM a lista não desconta (R$ 80 na lista, "Cupons - R$ 4", R$ 76 pagos).
    Com um item só, sai do valor dele. Com vários, repartir seria inventar: não envia.
  * Frete e total vêm do DETALHE: a lista não inclui o frete. "Frete grátis R$ 9,40"
    é o que se poupou, e o frete é 0. "Frete com desconto R$ 23,69 R$ 12,99": o pago
    é o último. "1x R$ 64,68" é parcelamento: parcelado ainda não foi visto.
  * Itens + frete têm de dar o total pago. Se não dão, a transação não é enviada e o
    log avisa: isso pega o caso que ainda não vimos, em vez de gravar errado.

O detalhe traz endereço fora do bloco da transação: guarda-se só esse bloco, e mesmo
nele linha com cara de endereço não passa. Compra a caminho não tem nome nem preço na
lista: entra quando chegar ao histórico.
"""
from __future__ import annotations

import json
import re
from datetime import date
from decimal import Decimal
from urllib.parse import parse_qs, urlparse

from .augustinus import conectar
from .base import RAIZ, carregar_json, log, salvar_json

LISTA = "https://myaccount.mercadolivre.com.br/my_purchases/list"
CACHE = RAIZ / "dados" / "compras-online.json"
LOJA = "mercado_livre"
MAX_DETALHES = 15  # por rodada: o resto fica para a próxima, e cada transação só abre uma vez

_MESES = {m: i for i, m in enumerate(("jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"), 1)}
_COMPRADO = re.compile(r"^(Comprado em .+?) \| R\$ ([\d.,]+)$")
_REAIS = re.compile(r"^R\$ ([\d.,]+)$")
_PAGO = re.compile(r"^(\d+)x R\$ ([\d.,]+)$")
_UNIDADES = re.compile(r"^(\d+) unidades?$", re.I)
_BARRADO = re.compile(r"captcha|n[aã]o sou um rob[oô]|/jms/|/login", re.I)
_CEP = re.compile(r"\b\d{5}-?\d{3}\b")
_ENDERECO = re.compile(r"\b(rua|r\.|av\.|avenida|alameda|travessa|apto?\.?|apartamento|bloco|cep|cpf|cnpj|cart[aã]o|"
                       r"final \d{4}|visa|mastercard|recebe|retirar|porteiro|portaria)\b", re.I)
# Cartão sem fronteira de palavra: a Amazon escreve "Mastercardterminando em NNNN" (medido em 09/11).
_PAGAMENTO = re.compile(r"mastercard|visa|hipercard|american express|amex|\belo\b|terminando em \d{4}|final \d{4}", re.I)


def reais(texto: str) -> Decimal:
    return Decimal(texto.replace(".", "").replace(",", "."))


def linhas_de(texto: str) -> list[str]:
    return [l.strip() for l in texto.splitlines() if l.strip()]


def seguras(linhas: list[str], proibidos: list[str]) -> list[str]:
    """Tira o que tem cara de endereço, documento ou cartão, e os termos do nao_publicar."""
    return [l for l in linhas if not (_CEP.search(l) or _ENDERECO.search(l) or _PAGAMENTO.search(l)
                                      or any(p in l.lower() for p in proibidos))]


def itens_da_lista(linhas: list[str], links: list[str]) -> list[dict]:
    """Os itens do histórico, cada um com o seu link "Ver detalhe", na ordem da página.

    Levanta ValueError se a contagem não bate: a página mudou, e casar título com o
    link errado grava o valor de uma compra na transação de outra.
    """
    itens = []
    for i, l in enumerate(linhas):
        m = _COMPRADO.match(l)
        if m and i:
            itens.append({"titulo": linhas[i - 1], "data_texto": m.group(1).removeprefix("Comprado em "),
                          "valor_total": reais(m.group(2)), "linha_lista": l})
    if len(itens) != len(links):
        raise ValueError(f"{len(itens)} compras e {len(links)} links na lista")
    for item, link in zip(itens, links):
        u = urlparse(link)
        ordem = parse_qs(u.query).get("orderId", [""])[0]
        partes = u.path.rstrip("/").split("/")
        if not ordem or len(partes) < 2:
            raise ValueError("link de detalhe em formato novo")
        item.update(pedido_externo=partes[-2], item_externo=ordem, url=u.path, link=link)
    return itens


def detalhe_da_transacao(linhas: list[str]) -> dict | None:
    """Frete, total pago e quantidades do bloco "Detalhes da transação"; None se não há o bloco."""
    if "Detalhes da transação" not in linhas:
        return None
    ini = linhas.index("Detalhes da transação") + 1
    if "Total pago" not in linhas[ini:]:
        return None
    pos = linhas.index("Total pago", ini)
    bloco = linhas[ini:pos + 2]
    numero = next((re.sub(r"\D", "", l) for l in bloco if l.startswith("#")), "")

    frete = None
    for k, l in enumerate(bloco):
        b = l.lower()
        if b == "frete grátis":  # o R$ que vem depois é o que se poupou
            frete = Decimal(0)
            break
        if b.startswith("frete"):
            valores = []
            for seguinte in bloco[k + 1:]:
                m = _REAIS.match(seguinte)
                if not m:
                    break
                valores.append(reais(m.group(1)))
            if valores:
                frete = valores[-1]  # com desconto vêm dois: o de tabela e o pago
            elif k + 1 < len(bloco) and "grátis" in bloco[k + 1].lower():
                frete = Decimal(0)
            break

    pago = _PAGO.match(bloco[-1])
    total = reais(pago.group(2)) if pago and pago.group(1) == "1" else None  # parcelado: não medido
    quantidades = {}
    for k, l in enumerate(bloco[:-1]):
        m = _UNIDADES.match(bloco[k + 1])
        if m:
            quantidades[l] = int(m.group(1))
    return {"numero": numero, "frete": frete, "total_pago": total, "quantidades": quantidades,
            "bloco": [l for l in bloco if not l.startswith("#")]}


def deduzir_data(texto: str, hoje: date) -> date | None:
    """A loja mostra "5 de set." sem ano: vale o ano que não põe a data no futuro (regra combinada com o Augustinus).

    É palpite, e erra em compra de mais de um ano: por isso data_texto vai junto, e a tela de lá confirma.
    Texto que não se reconhece dá None, nunca um chute.
    """
    m = re.match(r"^(\d{1,2}) de ([a-zç]{3})[a-zç]*\.?(?: de (\d{4}))?$", texto.strip().lower())
    if not m or m.group(2) not in _MESES:
        return None
    dia, mes = int(m.group(1)), _MESES[m.group(2)]
    for ano in ([int(m.group(3))] if m.group(3) else [hoje.year, hoje.year - 1, hoje.year - 2]):
        try:
            d = date(ano, mes, dia)
        except ValueError:  # 29/02 fora de ano bissexto, ou texto estragado
            continue
        if m.group(3) or d <= hoje:
            return d
    return None


def fecha(valores: list[Decimal], frete: Decimal | None, total: Decimal | None) -> bool:
    return total is not None and sum(valores, Decimal(0)) + (frete or 0) == total


def cupons_do_bloco(bloco: list[str]) -> Decimal:
    """O que o bloco diz de cupom: "Cupons" seguido de "- R$ 4". Do bloco, para valer também no cache."""
    total = Decimal(0)
    for l, seguinte in zip(bloco, bloco[1:]):
        m = re.match(r"^-\s*R\$ ([\d.,]+)$", seguinte)
        if m and l.lower().startswith("cupo"):
            total += reais(m.group(1))
    return total


def _para_cache(d: dict, proibidos: list[str]) -> dict:
    return {"frete": None if d["frete"] is None else str(d["frete"]),
            "total_pago": None if d["total_pago"] is None else str(d["total_pago"]),
            "quantidades": d["quantidades"], "bloco": seguras(d["bloco"], proibidos)}


def linhas_para_envio(itens: list[dict], detalhes: dict, conta: str, proibidos: list[str],
                      hoje: date | None = None) -> tuple[list[dict], list[str]]:
    """(linhas do insert, avisos). Transação que não fecha não sai, inteira."""
    hoje = hoje or date.today()
    por_transacao: dict[str, list[dict]] = {}
    for item in itens:
        por_transacao.setdefault(item["pedido_externo"], []).append(item)
    linhas, avisos = [], []
    for numero, grupo in por_transacao.items():
        d = detalhes.get(numero)
        if not d:
            continue  # detalhe ainda não aberto: fica para a próxima rodada
        frete = None if d["frete"] is None else Decimal(d["frete"])
        total = None if d["total_pago"] is None else Decimal(d["total_pago"])
        cupons = cupons_do_bloco(d["bloco"])
        if cupons and len(grupo) > 1:
            avisos.append(f"compra de {grupo[0]['data_texto']}: cupom em vários itens, sem como repartir; não enviada")
            continue
        valores = [i["valor_total"] - cupons for i in grupo]
        if not fecha(valores, frete, total):
            avisos.append(f"compra de {grupo[0]['data_texto']}: itens + frete não dão o total pago; não enviada")
            continue
        for i, valor in zip(grupo, valores):
            bruto = {"lista": i["linha_lista"], "detalhe": seguras(d["bloco"], proibidos)}
            linhas.append({"loja": LOJA, "conta": conta, "pedido_externo": numero, "item_externo": i["item_externo"],
                           "titulo": i["titulo"], "data_pedido": deduzir_data(i["data_texto"], hoje),
                           "data_texto": i["data_texto"],
                           "valor_total": valor, "frete": frete, "total_pago": total, "situacao": None,
                           "quantidade": d["quantidades"].get(i["titulo"]), "url": i["url"],
                           "bruto": json.dumps(bruto, ensure_ascii=False)})
    return linhas, avisos


def enviar(linhas: list[dict], acesso: dict) -> None:
    con = conectar(acesso)
    try:
        for l in linhas:
            con.run("insert into recebido.pedidos_online (loja, conta, pedido_externo, item_externo, titulo, "
                    "data_pedido, data_texto, valor_total, frete, total_pago, situacao, quantidade, url, bruto) "
                    "values (:loja, :conta, :pedido_externo, :item_externo, :titulo, cast(:data_pedido as date), "
                    ":data_texto, :valor_total, :frete, :total_pago, :situacao, :quantidade, :url, "
                    "cast(:bruto as jsonb)) on conflict do nothing", **l)
    finally:
        con.close()


# Compra a caminho também tem "Ver detalhe", mas sem "Comprado em": em 05/11 eram 15 links para 13
# compras, e a lista toda foi recusada. Cada link sobe até o maior bloco que só contém ele, e conta
# se esse bloco diz "Comprado em". A contagem em itens_da_lista continua de guarda.
_LINKS_DO_HISTORICO = """els => els.filter(a => /detalhe/i.test(a.innerText || '')).map(a => {
    const n = e => ((e.innerText || '').match(/ver detalhe/gi) || []).length;
    let card = a;
    while (card.parentElement && n(card.parentElement) <= 1) card = card.parentElement;
    return [/Comprado em/.test(card.innerText || ''), a.href];
})"""


def coletar(page, cache: dict, proibidos: list[str]) -> tuple[list[dict], list[str]]:
    """Lê a lista e abre o detalhe só de transação nova. Login ou captcha: para e avisa."""
    from .navegador import ir, texto

    ir(page, LISTA, espera=6)
    corpo = texto(page)
    if _BARRADO.search(page.url) or _BARRADO.search(corpo[:3000]):
        return [], ["Mercado Livre pediu login ou captcha na lista de compras; nada lido"]
    links = [h for no_historico, h in page.eval_on_selector_all("a", _LINKS_DO_HISTORICO) if no_historico]
    try:
        itens = itens_da_lista(linhas_de(corpo), links)
    except ValueError as e:
        return [], [f"lista de compras do Mercado Livre não reconhecida: {e}"]

    abertos, avisos = 0, []
    for item in itens:
        numero = item["pedido_externo"]
        if numero in cache or abertos >= MAX_DETALHES:
            continue
        abertos += 1
        ir(page, item["link"], espera=8)
        pagina = texto(page)
        if _BARRADO.search(page.url) or _BARRADO.search(pagina[:3000]):
            avisos.append("Mercado Livre pediu login ou captcha num detalhe; parei de abrir")
            break
        d = detalhe_da_transacao(linhas_de(pagina))
        if not d:
            avisos.append(f"detalhe da compra de {item['data_texto']} não reconhecido")
        elif d["numero"] != numero:
            avisos.append(f"compra de {item['data_texto']}: o número do detalhe não é o do link; ignorada")
        else:
            cache[numero] = _para_cache(d, proibidos)
    return itens, avisos


def rodar(cfg: dict, acesso: dict | None, proibidos: list[str], ensaio: bool) -> int:
    """Devolve quantas linhas saíram (ou sairiam, no ensaio). Sem exceção por loja fora do ar: avisa no log."""
    from .navegador import abrir_navegador

    from . import compras_amazon

    cache, cache_amz = carregar_json(CACHE, {}), carregar_json(compras_amazon.CACHE, {})
    pw, ctx = abrir_navegador(cfg, visivel=False)
    try:
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        itens, avisos = coletar(page, cache, proibidos)
        try:  # uma loja quebrada não leva a outra junto
            pedidos_amz, avisos_amz = compras_amazon.coletar(page, cache_amz, proibidos)
        except Exception as exc:
            pedidos_amz, avisos_amz = [], [f"Amazon: ERRO {type(exc).__name__}"]
    finally:
        ctx.close()
        pw.stop()
    salvar_json(CACHE, cache)
    salvar_json(compras_amazon.CACHE, cache_amz)
    conta = (acesso or {}).get("conta", "danilo")
    linhas, a2 = linhas_para_envio(itens, cache, conta, proibidos)
    linhas_amz, a3 = compras_amazon.linhas_para_envio(pedidos_amz, cache_amz, conta, proibidos)
    linhas += linhas_amz
    itens = itens + pedidos_amz  # para a contagem e para marcar o dia: basta uma loja ter lido
    for a in avisos + a2 + avisos_amz + a3:
        log("Compras online: " + a)
    if ensaio:
        for l in linhas:
            frete = "?" if l["frete"] is None else l["frete"]
            print(f"  {l['data_texto']:>12} | R$ {l['valor_total']:>8} | frete {frete} | total {l['total_pago']} "
                  f"| qtd {l['quantidade']} | {l['titulo'][:50]}")
        log(f"Compras online (ensaio, nada enviado): {len(linhas)} linhas de {len(itens)} itens lidos.")
        return len(linhas)
    if not acesso:
        log("Compras online: falta a seção [augustinus_pedidos] no local.toml; nada enviado.")
        return 0
    if linhas:
        enviar(linhas, acesso)
    log(f"Compras online: {len(linhas)} linhas entregues ao Augustinus, de {len(itens)} itens lidos.")
    if itens:  # loja barrada não conta como entregue: a próxima rodada tenta de novo
        cache["_ultima_entrega"] = date.today().isoformat()
        salvar_json(CACHE, cache)
    return len(linhas)


def entregue_hoje(hoje: date | None = None, cache: dict | None = None) -> bool:
    """A rodada do logon entrega no máximo uma vez por dia; a linha de comando não pergunta."""
    cache = carregar_json(CACHE, {}) if cache is None else cache
    return cache.get("_ultima_entrega") == (hoje or date.today()).isoformat()
