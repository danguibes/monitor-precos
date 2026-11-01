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
| `py monitor.py --pedidos` | atende os pedidos do formulário e roda já os monitores criados |
| `py monitor.py --vigiar` | o vigia: olha o GitHub a cada `vigia_minutos` (o lançador chama depois do `--logon`) |
| `py instalar.py --remover` | tira o lançador da pasta Inicializar |

## Monitores: o rol de produtos

**O jeito fácil é o formulário.** O botão "+ Novo monitor" da página abre um
formulário no GitHub (funciona no celular): nome, como procurar, o que precisa
e o que não pode conter, tamanho, quantas unidades comparar. Tudo em palavras —
"com gás ou gaseificada" vira a regra, acento e maiúscula não importam. Com o
notebook ligado, em até 5 minutos o vigia percebe o pedido; o notebook lê o pedido, cria `monitores/<id>.toml`, valida, faz
commit só desse arquivo, responde no pedido e o fecha; se algo não fizer
sentido, responde o problema e deixa o pedido aberto. **Só pedidos do dono do
repositório são atendidos**; os de outra conta ficam intocados e aparecem como
aviso na página inicial. O "editar" de cada monitor criado assim reabre o
formulário preenchido. Para atender os pedidos na hora, pelo notebook:
`py monitor.py --pedidos`.

**Pausar, retomar e excluir** ficam no card de cada monitor, na página inicial.
Cada link abre um formulário já preenchido (rótulo `gerenciar-monitor`), e o
vigia o atende como um pedido. **Pausado** (`pausado = true` no toml) continua na
página, apagado e com a etiqueta "pausado", com os últimos preços, mas fica fora
das rodadas: só `py monitor.py --monitor <id>` ainda o consulta. **Excluir** apaga
`monitores/<id>.toml` num commit; o histórico em `dados/<id>/` fica no notebook,
e o arquivo volta pelo histórico do git. (`desligado = true` some da página
também, e só se põe à mão.)

## Atualizar agora, e o vigia

O botão **"↻ Atualizar agora"** da página abre uma issue com o rótulo
`atualizar`. Depois da rodada do logon, o lançador deixa um **vigia** rodando:
a cada `vigia_minutos` (config.toml, padrão 5) ele faz **uma** consulta às
issues abertas do repositório.

- `atualizar` do dono: roda todos os monitores (sem abrir o relatório), publica,
  comenta a hora na issue e a fecha.
- `novo-monitor` do dono: roda `--pedidos`, que cria o monitor e já o pesquisa.
- Issue de outra conta: não dispara nada; vira uma linha no `monitor.log`.

Custo: um processo `pythonw` de ~25 MB, que dorme entre as consultas (288
chamadas por dia, contra o limite de 5.000 por hora da API do GitHub) e não
impede o notebook de suspender. O texto da issue nunca é lido; só o rótulo e o
autor. Sem rede, cada falha vira uma linha no log e ele tenta de novo depois. Um
segundo vigia não sobe (trava em `dados/vigia.lock`). Com o notebook desligado,
o pedido espera o próximo logon.

**Token só deste repositório.** Com `[github] token` no `local.toml` (um token
"fine-grained" com acesso só ao monitor-precos, Contents e Issues em leitura e
escrita), o monitor e o vigia usam só ele: `GH_TOKEN` para o `gh`, e para o `git`
o token no cabeçalho, com a configuração de sistema ignorada e reposta sem as
linhas `credential.*` (o Git Credential Manager tem o login que alcança todos os
repositórios). Medido em 31/10: monitor-precos lê e empurra; yves e oclandestino
dão 404 no `gh` e 403 no `git`. O log diz qual login o vigia usa ao subir. O token
vence: quando vencer, as consultas falham com uma linha no log.

Para parar o vigia até o próximo logon, encerre o `pythonw.exe` cuja linha de
comando tem `--vigiar` (Gerenciador de Tarefas → Detalhes, coluna "Linha de
comando"). Para não ligá-lo mais: `vigia_minutos = 0` no config.toml.

Cada monitor é um arquivo em `monitores/`, em TOML (aceita comentários), e
também pode ser escrito à mão — o modelo comentado está em `modelos/monitor.toml`.
O monitor faz `git pull` antes de cada rodada, e o Actions acusa se o arquivo quebrou.

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

**Mercado Livre pela API oficial, nos monitores de marca.** Com `mercado_livre =
"ambos"` no toml (hoje: freezer e os quatro colchões), o catálogo do Mercado Livre
vem também pela API — sem navegador, sem login, sem captcha —, além do navegador;
`"api"` usa só a API. Medido em 01/11 com o app próprio (credenciais em
`[mercadolivre]` do `local.toml`; `ferramentas/sonda_api_meli.py` repete a medição):

- a busca aberta (`/sites/MLB/search`) e a ficha do anúncio (`/items/{id}`) dão 403
  mesmo com token — por isso só **produto de catálogo** entra;
- `/products/search` e `/products/{id}/items` respondem com o token do app;
- o frete para o CEP (`/items/{id}/shipping_options`) responde **sem** token, e dá
  403 com ele.

O catálogo não tem tudo: no Emma, os colchões avulsos estavam no catálogo **sem
anúncio**, e o anúncio de R$ 1.514,97 que o navegador achou estava fora dele — por
isso "ambos" e não "api". No Guldi, o navegador trouxe zero numa rodada e a API onze.
Sem acesso à API, o navegador segue e a página avisa. Editar o monitor pelo
formulário preserva `mercado_livre`, `pausado`, `unidade_nome` e `limiar_augustinus`.

**Página com variantes no Mercado Livre (navegador).** Colchão e outros produtos
com tamanho ou cor trazem o JSON-LD como `ProductGroup`, um preço por variante.
Até 01/11 o leitor só conhecia `Product`, e **todo colchão dava zero ofertas,
calado**. Agora vale a variante com o id da página (`/p/MLB…`); senão a mais barata
cujo nome passa nas regras do monitor (que tiram queen, king, solteiro), abrindo a
página dela; senão nenhuma — nunca o preço de outro tamanho.

**Lojas em que o monitor entra com a sua conta** (Mercado Livre, Vila das
Frutas) esperam `pausa_lojas_com_login` segundos a mais por página (6, em
config.toml): um bloqueio ali não fica na loja, chega à conta. Ao ampliar para
muitos produtos, olhe o monitor.log atrás de "captcha" e "pede login".


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

## Unidade de comparação

Cada monitor compara numa unidade só, a mesma na página e no Augustinus:

- **litro**, quando o monitor tem `volume_ml` (água);
- **unidade**, nos outros casos. Com `montar_pack`, o anúncio vira o pack
  inteiro, e o total já é comparável (papel: 12 rolos). **Sem pack, os pacotes
  variam** (lenço: 16, 50, 88), então a melhor oferta de cada loja é a de
  **menor total por unidade**, e o anúncio que não diz quantas unidades traz não
  ganha. A contagem vem do título: "50 un", "16 folhas", "400 lenços".
  **Kit, combo ou "N pacotes"** é ambíguo — "Kit 3 pacotes 150 unidades" pode ser
  150 no total ou por pacote, e o vendedor não diz. A conta usa o número do título
  sem multiplicar (o menor total: o kit nunca parece mais barato do que é), e a
  oferta ganha a etiqueta **"⚠ kit: confira a quantidade"**. O nome da unidade é "un." por padrão (`unidade_nome = "rolo"` no toml
  muda).

## Comparação com o Augustinus

A cada rodada, o monitor lê uma vez o que a casa pagou no supermercado, pelo
Augustinus (a view `monitor.compras_da_casa`, com um papel de banco que só lê
ela). Para cada monitor ele calcula a **mediana do último ano** na unidade do
monitor:

- **litro**: o volume vem do catálogo do Augustinus, nunca do texto do cupom
  ("AGUA MINMINALBA 15L" é 1,5 L).
- **unidade**: a contagem vem do cupom ("C/4", "11RL", "L16P15"), e a compra
  que não traz contagem fica de fora.
- Sem regra "precisa conter", a compra precisa ter todas as palavras de um dos
  termos de busca. Compra a peso nunca entra. Monitor acompanhado (o freezer)
  não tem referência.

**No topo à direita**, uma vez por página: quanto a casa paga (a mediana), a
melhor oferta daqui na mesma unidade, com o frete, e um link para cada conceito
do Augustinus por trás da conta. Quando as compras se espalham por vários
conceitos (papel: "folha dupla", "folha dupla neutro" e o genérico), aparecem
até três, com o de nome mais parecido com o monitor primeiro. Os links pedem
login.

No card, só a marca **"▼ abaixo do que você paga"**, quando a oferta, já com
frete, sai pelo menos 10% abaixo da mediana (`limiar_augustinus = 0.15` no toml
muda o corte).

Credenciais na seção `[augustinus]` do `local.toml` (host, porta, usuario,
senha, banco, app). Sem essa seção, ou com o banco fora do ar, o monitor segue
normalmente e mantém a última referência.

## Nuvem ou casa: o que foi medido (31/10/2026)

`ferramentas/sonda_ip.py` (requisição simples) e `ferramentas/sonda_navegador.py`
(o Chrome aberto como o monitor abre, perfil novo e sem login, duas passadas)
rodaram daqui (Claro, residencial) e de um servidor do GitHub Actions (Microsoft,
EUA), com CEP genérico. Pelo navegador:

| loja | casa | nuvem |
|---|---|---|
| Amazon, Vila das Frutas | produtos | produtos |
| Mercado Livre | produtos (sem login) | captcha |
| Magalu | produtos | "Não é possível acessar a página" (403) |
| Carrefour | produtos | "Acesso Bloqueado" (403) |
| Casas Bahia | produtos; 403 na 2ª passada | página vazia |

VTEX e Pão de Açúcar, por API, respondem igual nos dois. Mudaram dois fatores
juntos (o IP e o sistema, Windows aqui e Linux lá), e a nuvem medida foi nos EUA,
não em São Paulo. Sem as duas opções de `navegador.py` que escondem a automação,
o Magalu recusa até daqui, e o Mercado Livre pede captcha.



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
  pedidos.py            o formulário "Novo monitor": pedido do GitHub vira monitores/<id>.toml
  vigia.py              o botão "Atualizar agora" e os pedidos, atendidos em até 5 minutos
  augustinus.py         o que a casa paga, para o selo "abaixo do que você paga"
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
