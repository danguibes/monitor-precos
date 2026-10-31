# Monitor de preços

Monitor pessoal de **preço, preço no Pix e frete para um CEP**, com histórico e
relatório em HTML. Nasceu acompanhando freezers (`monitor-freezer`, outubro de
2026) e está sendo generalizado para qualquer produto.

Uso pessoal: pausa de 0,4 s entre requisições, um navegador comum para as lojas
que exigem um, e **nenhum contorno de captcha**. Loja que barrar fica desligada.

**O código é público; o que é pessoal fica na máquina que coleta.** O CEP mora em
`local.toml` e os logins no perfil do navegador, os dois fora do git. A coleta
roda sempre nesta máquina, e ao fim de cada rodada os relatórios vão para o
GitHub Pages **sem o CEP** — uma varredura barra a publicação se achar o CEP ou
qualquer termo da lista `nao_publicar` de `local.toml`.

## Instalação (uma vez)

Na pasta do projeto:

```
py instalar.py
```

Ele pergunta o CEP e cria o `local.toml`, instala o Playwright, põe o lançador `Monitor de Precos.pyw` na pasta
Inicializar do Windows (`shell:startup`), abre o **navegador do monitor** para
você entrar no Mercado Livre e faz a primeira consulta. Toda a automação é em
Python, porque este notebook bloqueia `.bat` e PowerShell.

O navegador do monitor é o Chrome instalado, com perfil próprio em
`dados\perfil-navegador\`, separado do seu Chrome do dia a dia. O frete do
Mercado Livre usa o endereço padrão da conta: confira que é o de casa.

Mudou a pasta de lugar? Rode `py instalar.py --lancador`: o lançador guarda o
caminho absoluto e, sem isso, o monitor para de rodar no logon sem avisar.

## Comandos

| comando | o que faz |
|---|---|
| `py monitor.py` | consulta o freezer agora e abre o relatório |
| `py monitor.py --monitor agua-com-gas` | o mesmo, para outro monitor (`monitores/<id>.toml`) |
| `py monitor.py --todos` | todos os monitores |
| `py monitor.py --logon` | o que o lançador roda: `git pull`, depois todos os monitores, cada um pulando se a última consulta é mais recente que o seu `intervalo_minimo_horas`, e só abre o relatório se algum preço caiu |
| `py monitor.py --relatorio` | só regera e abre o relatório |
| `py monitor.py --configurar` | abre o navegador do monitor, visível, para login, CEP e verificação anti-robô |
| `py monitor.py --configurar viladasfrutas` | o mesmo, só com as páginas cujo endereço contém o termo |
| `py monitor.py --sem-navegador` | só as lojas por API (rápido) |
| `py monitor.py --publicar` | só republica os relatórios no GitHub Pages |
| `py monitor.py --nao-publicar` | coleta sem publicar |
| `py instalar.py --remover` | tira o lançador da pasta Inicializar |

## Monitores: o rol de produtos

Cada monitor é um arquivo em `monitores/`, em TOML (aceita comentários). Para
criar um, copie o mais parecido e troque o que procurar. Dá para fazer **pelo
site do GitHub, inclusive no celular**: o monitor faz `git pull` antes de cada
rodada, e o Actions acusa se o arquivo quebrou.

| monitor | arquivo | modo | dados em |
|---|---|---|---|
| freezer | `monitores/freezer.toml` | acompanhado: modelos fixos, regex por modelo | `dados/` |
| água com gás 6 × 1,5 L | `monitores/agua-com-gas.toml` | descoberta: busca aberta, entra o que passa nas regras | `dados/agua-com-gas/` |

**Nenhum monitor escolhe lojas.** Todos pesquisam todas as lojas de `lojas.toml`;
a loja que não vende o produto só não devolve oferta.

No **modo descoberta** o monitor define `termos` amplos de busca e `regras`:
`incluir` e `excluir` (regex), `volume_ml` (de uma unidade) e `montar_pack`. Com
`montar_pack = 6`, a comparação é **o custo de receber 6 unidades**: 6 avulsas,
2 kits de 3 ou um pack de 6, com o frete contado uma vez. Um pack de 12 não
entra, porque obrigaria a comprar 12. O relatório tem um card por loja e a
coluna total por litro.

No **modo acompanhado** cada item de `produtos` tem `busca` (o termo) e `padrao`
(regex que precisa aparecer no anúncio **e** na página do produto).

## Lojas

| como | lojas |
|---|---|
| API pública VTEX, sem navegador | Electrolux, Fast Shop, Consul, Brastemp, Compra Certa, Midea; mercados: Mambo, Atacadão, Oba Hortifruti |
| API própria, sem navegador | Pão de Açúcar (a loja que atende o CEP sai de `deliveryOptions`) |
| navegador real | Carrefour, Magalu, Casas Bahia, Mercado Livre; Vila das Frutas (com login) |
| desligada | Shopee (captcha no navegador; o caminho é a API oficial de afiliados) |
| fora por enquanto | Assaí (só vende online por iFood e Rappi, que pedem app e login) |

Medido em 30/10/2026 para o CEP de casa: Zaffari, Covabra e Savegnago também
são VTEX, mas não entregam aqui. Na Sua Casa por Coca-Cola (VTEX, só a
engarrafadora Andina) também não: atende só o Rio.

**Achadas pelo Google Shopping e medidas pela interface do site em 30/10/2026:**

- **Hirota** (`lojahirota.com.br`, VipCommerce): para o CEP de casa o site
  responde `cepAtendido: true, apenasRetirada: true` — **só retirada**, na loja
  mais próxima. Não entrega aqui.
- **Vila das Frutas** (`viladasfrutas.com.br`, osuper): os preços abrem sem
  conta, mas **a opção Entrega exige login**. **Entrou** com a conta do dono no
  perfil do monitor (`py monitor.py --configurar viladasfrutas`), em modo Entrega
  pela loja que atende o CEP: R$ 15,00 por horário agendado, grátis acima de R$ 350. O
  coletor lê o texto da página — o cabeçalho logado tem o endereço completo da
  conta, e só a taxa e o horário saem dele. Se a sessão cair, o aviso no rodapé
  do relatório diz "pede login".

O Google Shopping serve para **achar lojas**, não como fonte de preço: mostra o
preço sem o frete do CEP e mistura lojas que não entregam aqui. **O pedido mínimo dos mercados não aparece em
nenhuma das APIs**, então uma oferta barata pode exigir completar a cesta.

Ofertas sem frete conhecido ficam na tabela, mas não ganham o card de melhor oferta.

## Arquivos

```
monitor.py              entrada
instalar.py             instalação e lançador
config.toml             opções gerais (intervalo, publicar)
lojas.toml              o registro único de lojas, que vale para todos os monitores
monitores/<id>.toml     o rol: um arquivo por monitor
local.toml              o CEP e a lista nao_publicar — fora do git (modelo: local.exemplo.toml)
precos/                 o código
  base.py               caminhos e utilidades
  coleta.py             orquestra as lojas
  filtros.py            o anúncio é do modelo? (ou passa nas regras?)
  monitores.py          carrega os monitores
  unidades.py           quantidade e volume no título; montagem do pack
  historico.py          CSV
  relatorio.py          HTML (a versão local e a pública, sem CEP)
  publicar.py           GitHub Pages: gera, varre e empurra para gh-pages
  navegador.py          o Chrome do monitor
  lojas/<loja>.py       um módulo por loja
tests/                  testes offline
  fixtures/<loja>/      respostas reais salvas das lojas
ferramentas/
  salvar_fixture.py     captura uma resposta real para virar fixture
dados/                  tudo o que é gerado — fora do git
```

Em `dados/`: `historico.csv` (Excel, separador `;`), `relatorio.html`,
`estado.json` (canal de vendas de cada loja VTEX, última execução),
`monitor.log`, `perfil-navegador/` e `site/` (a cópia que vai para o Pages).

## Testes

```
py -m pip install pytest
py -m pytest
```

Os testes rodam contra respostas reais salvas em `tests/fixtures/`, sem rede.
Cada arquivo de teste é de uma loja, então o nome do teste que falha diz qual
loja mudou de layout. Para atualizar uma fixture:

```
py ferramentas/salvar_fixture.py vtex <host> <sku> <vendedor> <nome>
py ferramentas/salvar_fixture.py pagina <loja> <url> <nome> [--cep]
```

As fixtures usam um **CEP neutro** (Av. Paulista), não o de casa, e um teste
varre o repositório atrás do CEP de `local.toml`.

O GitHub Actions roda só os testes, nunca uma coleta real.

## Se algo parar

- "pede login": `py monitor.py --configurar` e entre de novo.
- Casas Bahia "bloqueio anti-robô": `--configurar`, abra a Casas Bahia e passe a verificação.
- Os avisos de cada rodada aparecem no rodapé do relatório e em `dados\monitor.log`.
