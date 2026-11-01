"""Guardas sobre o próprio código.

Em 01/11/2026 apareceu em precos/monitores.py uma SEGUNDA definição de
usar_token_do_monitor — a versão antiga, que quebra o git no Windows. Em Python a
segunda definição vence em silêncio, e o primeiro sinal teria sido o git falhar
na rodada seguinte do vigia.
"""
import ast
from collections import Counter
from pathlib import Path

RAIZ = Path(__file__).parent.parent


def test_nenhuma_funcao_definida_duas_vezes_no_mesmo_arquivo():
    repetidas = []
    for arq in [RAIZ / "monitor.py", RAIZ / "instalar.py", *sorted((RAIZ / "precos").rglob("*.py"))]:
        arvore = ast.parse(arq.read_text(encoding="utf-8"))
        nomes = Counter(n.name for n in arvore.body if isinstance(n, (ast.FunctionDef, ast.ClassDef)))
        repetidas += [f"{arq.relative_to(RAIZ)}: {nome}" for nome, n in nomes.items() if n > 1]
    assert not repetidas, repetidas
