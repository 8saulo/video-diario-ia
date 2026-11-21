"""Escolha de tema: nunca repetir o mesmo assunto dito com outras palavras, nem cair na reserva já usada."""
import datetime as dt

from videobot import research

HOJE = dt.date(2026, 11, 21)
HIST = [{"data": "2026-11-18", "tema": "Consumo energético da IA"},
        {"data": "2026-11-19", "tema": "IA e empregos: o que os dados mostram"},
        {"data": "2026-11-20", "tema": "Consumo energético da IA"}]


def _cfg(reserva):
    return {"tema": {"nao_repetir_dias": 7, "temas_reserva": reserva, "nicho": "IA"}}


def test_mesmo_assunto_com_outras_palavras_conta_como_repetido():
    """Run de 21/11: 'Quanto de energia a IA realmente gasta' passou pelo veto porque o histórico guardou 'Consumo energético da IA'."""
    assert research._repetido("Quanto de energia a IA realmente gasta", HIST, HOJE, 7)
    assert research._repetido("Data centers e a conta de luz", HIST, HOJE, 7)
    assert not research._repetido("Deepfakes: como reconhecer um vídeo falso", HIST, HOJE, 7)
    assert not research._repetido("Modelos de IA abertos vs fechados", HIST, HOJE, 7)


def test_veto_tambem_olha_o_tema_da_pesquisa_gravado_no_historico():
    """O roteiro reescreve o tema; o texto original da reserva/pesquisa (tema_pesquisa) também bloqueia."""
    h = [{"data": "2026-11-20", "tema": "O preço oculto dos assistentes", "tema_pesquisa": "Chips de IA: por que a Nvidia vale tanto"}]
    assert research._repetido("Chips de IA: por que a Nvidia vale tanto", h, HOJE, 7)


def test_reserva_pula_temas_usados_na_semana():
    """A reserva só oferece o que não foi usado nos últimos 7 dias."""
    ordem = research.temas_reserva(_cfg(["Quanto de energia a IA realmente gasta", "Deepfakes: como reconhecer um vídeo falso",
                                         "IA e empregos: o que os dados mostram"]), HIST, HOJE)
    assert ordem == ["Deepfakes: como reconhecer um vídeo falso"]


def test_reserva_esgotada_pede_temas_novos_e_nao_poe_o_de_ontem_primeiro(monkeypatch):
    """Antes, com a reserva toda usada, voltava a lista inteira e podia repetir o tema de ontem."""
    monkeypatch.setattr(research, "gerar_json", lambda *a, **k: (["Consumo de energia das IAs", "Golpes com voz clonada"], {}, "falso"))
    ordem = research.temas_reserva(_cfg(["Quanto de energia a IA realmente gasta", "IA e empregos: o que os dados mostram"]), HIST, HOJE)
    assert ordem[0] == "Golpes com voz clonada", "o tema novo da IA vem primeiro, e o parecido com energia é descartado"
    assert ordem[1:] == ["IA e empregos: o que os dados mostram", "Quanto de energia a IA realmente gasta"], \
        "na última reserva, o menos usado recentemente vem antes"


def test_pesquisa_sem_chave_usa_autorizacao_do_canal(monkeypatch):
    """No GitHub sem YOUTUBE_API_KEY as páginas públicas voltam 0 vídeos; a pesquisa usa o OAuth do canal (Bearer)."""
    import videobot.youtube as yt
    env = {"YT_REFRESH_TOKEN": "rt"}
    monkeypatch.setattr(research, "chave", lambda n: env.get(n, ""))
    monkeypatch.setattr(yt, "_token", lambda: "tok")
    usadas = []
    monkeypatch.setattr(research, "via_api", lambda b, j, p, key: usadas.append(key) or [])
    monkeypatch.setattr(research, "via_paginas", lambda *a: [])
    monkeypatch.setattr(research, "temas_reserva", lambda *a: ["X"])
    cfg = {"tema": {"buscas": ["ai"] * 12, "temas_reserva": ["X"]}}
    out = research.pesquisar(cfg, [], HOJE)
    assert usadas == ["Bearer tok"]
    assert out["ranking"][0]["tema"] == "X"


def test_api_manda_bearer_no_cabecalho_authorization(monkeypatch):
    """Com token OAuth, o pedido vai em Authorization, não como chave de API."""
    visto = {}

    class R:
        def raise_for_status(self):
            pass

        def json(self):
            return {}

    monkeypatch.setattr(research.requests, "get", lambda url, params, headers, timeout: visto.update(headers) or R())
    research._api("search", {}, "Bearer tok")
    assert visto == {"Authorization": "Bearer tok"}


def test_workflow_passa_autorizacao_do_canal_para_a_geracao():
    """A etapa 'Gerar vídeo' precisa dos secrets YT_* para pesquisar sem YOUTUBE_API_KEY."""
    from pathlib import Path
    wf = (Path(__file__).resolve().parents[1] / ".github" / "workflows" / "video-diario.yml").read_text(encoding="utf-8")
    gerar = wf.split("- name: Gerar vídeo", 1)[1].split("- name:", 1)[0]
    for n in ("YT_CLIENT_ID", "YT_CLIENT_SECRET", "YT_REFRESH_TOKEN"):
        assert n in gerar
