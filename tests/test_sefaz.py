"""A guarda antes de gravar a página da SEFAZ. Chave e conteúdo inventados."""
from precos.sefaz import _SO_SEFAZ, problema_da_pagina

CHAVE = "3526" + "1" * 40
TEXTO = "Consulta Resumida NFC-e\nCódigo: 1\nValor a pagar R$: 10,00\nChave de acesso: 3526 " + "1111 " * 10


def test_nota_completa_passa():
    assert problema_da_pagina(200, "<html>ok</html>", TEXTO, CHAVE) is None


def test_captcha_nao_grava():
    assert problema_da_pagina(200, "<div class='g-recaptcha'>", TEXTO, CHAVE) == "captcha"


def test_rejeicao_do_f5_nao_grava():
    assert problema_da_pagina(200, "<title>Request Rejected</title>", "", CHAVE) == "rejeitada pela SEFAZ"


def test_pagina_sem_valor_ou_de_outra_nota_nao_grava():
    assert problema_da_pagina(200, "", TEXTO.replace("Valor a pagar", "Total"), CHAVE) == "sem o valor da nota"
    assert problema_da_pagina(200, "", TEXTO, "3526" + "2" * 40) == "a chave não está na página"


def test_status_diferente_de_200():
    assert problema_da_pagina(502, "", TEXTO, CHAVE) == "status 502"


def test_so_abre_endereco_da_sefaz_sp():
    assert _SO_SEFAZ.match("https://www.nfce.fazenda.sp.gov.br/qrcode?p=1|2")
    assert _SO_SEFAZ.match("https://www.nfce.fazenda.sp.gov.br/NFCeConsultaPublica/Paginas/ConsultaQRCode.aspx?1")
    assert not _SO_SEFAZ.match("https://exemplo.com/?u=https://www.nfce.fazenda.sp.gov.br/")
