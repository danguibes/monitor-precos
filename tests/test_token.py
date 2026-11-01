"""O token do monitor vale só para este processo e para o git/gh que ele chama."""
import os

from precos.monitores import usar_token_do_monitor


def test_sem_token_nada_muda(monkeypatch):
    monkeypatch.delenv("GH_TOKEN", raising=False)
    assert usar_token_do_monitor({}) is False and "GH_TOKEN" not in os.environ


def test_com_token_gh_e_git_usam_ele(monkeypatch):
    import base64
    for k in [k for k in os.environ if k.startswith(("GIT_CONFIG", "GH_TOKEN", "GCM_"))]:
        monkeypatch.delenv(k)
    for k in ("GH_TOKEN", "GIT_CONFIG_NOSYSTEM", "GIT_CONFIG_COUNT", "GCM_INTERACTIVE"):
        monkeypatch.setenv(k, "x"); monkeypatch.delenv(k)  # o monkeypatch desfaz no fim
    for i in range(40):
        monkeypatch.setenv(f"GIT_CONFIG_KEY_{i}", "x"); monkeypatch.delenv(f"GIT_CONFIG_KEY_{i}")
        monkeypatch.setenv(f"GIT_CONFIG_VALUE_{i}", "x"); monkeypatch.delenv(f"GIT_CONFIG_VALUE_{i}")
    assert usar_token_do_monitor({"github": {"token": " github_pat_x "}}) is True
    assert os.environ["GH_TOKEN"] == "github_pat_x" and os.environ["GIT_CONFIG_NOSYSTEM"] == "1"
    pares = {os.environ[f"GIT_CONFIG_KEY_{i}"]: os.environ[f"GIT_CONFIG_VALUE_{i}"]
             for i in range(int(os.environ["GIT_CONFIG_COUNT"]))}
    assert not any(k.lower().startswith("credential.") for k in pares)          # o login amplo fica de fora
    assert all(pares.values())                                                   # nada vazio (Windows)
    cabecalho = pares["http.https://github.com/.extraheader"].removeprefix("AUTHORIZATION: basic ")
    assert base64.b64decode(cabecalho).decode() == "x-access-token:github_pat_x"
