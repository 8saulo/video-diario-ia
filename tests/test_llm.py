"""Regressões da cadeia de IAs de texto (videobot/llm.py)."""
from __future__ import annotations

import pytest

from videobot import llm


@pytest.fixture(autouse=True)
def isolar(monkeypatch):
    llm._fora.clear()
    monkeypatch.setattr(llm, "disponiveis", lambda cfg: ["groq", "openrouter"])
    monkeypatch.setattr(llm, "_ordenar", lambda prov, cfg: [m for m in (f"{prov}-a", f"{prov}-b") if f"{prov}/{m}" not in llm._fora])
    monkeypatch.setattr(llm.time, "sleep", lambda s: None)
    yield
    llm._fora.clear()


def test_limite_por_minuto_em_todos_faz_nova_rodada(monkeypatch, cfg):
    """Erro de 11/11/2026: todos deram 429 passageiro no pedido de correção e o roteiro falhou."""
    chamadas = []

    def falso(prov, m, msgs, t, mt):
        chamadas.append(m)
        return (429, "", 0.0, "Provider returned error") if len(chamadas) <= 4 else (200, "certo", 0.0, "")

    monkeypatch.setattr(llm, "_openai", falso)
    assert llm.gerar("x", cfg) == ("certo", "groq/groq-a")
    assert not llm._fora, "429 passageiro não pode tirar o modelo da execução"


def test_cota_do_dia_nao_espera_rodada_extra(monkeypatch, cfg):
    esperas = []
    monkeypatch.setattr(llm.time, "sleep", lambda s: esperas.append(s))
    monkeypatch.setattr(llm, "_openai", lambda *a: (429, "", 0.0, "Rate limit reached: tokens per day (TPD)"))
    with pytest.raises(RuntimeError):
        llm.gerar("x", cfg)
    assert 60 not in esperas


def test_pedido_grande_demais_nao_tira_modelo(monkeypatch, cfg):
    monkeypatch.setattr(llm, "_openai", lambda *a: (400, "", 0.0, "Please reduce the length of the messages or completion."))
    with pytest.raises(RuntimeError):
        llm.gerar("x", cfg)
    assert not llm._fora


def test_resposta_vazia_explica_o_motivo(monkeypatch):
    """Os modelos que 'pensam' devolviam content vazio e o log só dizia 'HTTP 200'."""
    class R:
        status_code = 200
        headers = {}

        def json(self):
            return {"choices": [{"message": {"content": ""}, "finish_reason": "length"}]}

    enviados = {}
    monkeypatch.setattr(llm, "chave", lambda n: "x")
    monkeypatch.setattr(llm.requests, "post", lambda url, headers, json, timeout: enviados.update(json) or R())
    st, txt, _, msg = llm._openai("openrouter", "nvidia/nemotron:free", [{"role": "user", "content": "x"}], 0.2, 100)
    assert st == 200 and txt == "" and "pensando" in msg
    assert enviados["reasoning"] == {"effort": "low", "exclude": True}
