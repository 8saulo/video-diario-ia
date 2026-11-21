"""Regressões do pipeline e do render (sem rede e sem Chromium)."""
from __future__ import annotations

import sys
import types

import pytest

from videobot import pipeline, render


def test_refazer_usa_a_paleta_do_video_original(monkeypatch, cfg):
    monkeypatch.setattr(pipeline, "historico", lambda: [
        {"slug": "outro", "paleta": "laranja"}, {"slug": "data_centers", "paleta": "azul"}])
    pipeline._paleta_do_slug(cfg, "data_centers")
    assert cfg["visual"]["paleta"] == "azul"


def test_chromium_que_nao_abre_e_reinstalado(monkeypatch):
    """11/11/2026: às 02:00 o Playwright não achou o executável do Chromium e o vídeo local falhou."""
    tentativas, instalou = [], []

    class Br:
        def new_page(self, **k):
            pg = types.SimpleNamespace(goto=lambda u: None, wait_for_function=lambda s: None)
            return pg

    class Chromium:
        def launch(self, args):
            tentativas.append(1)
            if len(tentativas) == 1:
                raise RuntimeError("BrowserType.launch: Executable doesn't exist")
            return Br()

    pw = types.SimpleNamespace(chromium=Chromium(), stop=lambda: None)
    fake = types.ModuleType("playwright.sync_api")
    fake.sync_playwright = lambda: types.SimpleNamespace(start=lambda: pw)
    monkeypatch.setitem(sys.modules, "playwright.sync_api", fake)
    monkeypatch.setattr(render.subprocess, "run", lambda cmd, **k: instalou.append(cmd))
    import time
    monkeypatch.setattr(time, "sleep", lambda s: None)
    render._abrir(100, 100)
    assert len(tentativas) == 2
    assert instalou and "install" in instalou[0]


class _ChegouNoRoteiro(Exception):
    pass


def _preparar_pipeline(monkeypatch):
    from videobot import facts, llm, research, script
    monkeypatch.setattr(llm, "disponiveis", lambda cfg: ["groq"])
    monkeypatch.setattr(research, "pesquisar", lambda cfg, hist, data: {"ranking": [{"tema": "FTTH", "titulo": ""}]})
    monkeypatch.setattr(facts, "coletar", lambda cand, cfg: {"ok": False, "motivo": "só 1 fonte", "fatos": [], "cortados": []})

    def roteiro(*a, **k):
        raise _ChegouNoRoteiro()
    monkeypatch.setattr(script, "escrever", roteiro)
    monkeypatch.setattr(pipeline, "historico", lambda: [])


def test_sem_crivo_segue_mesmo_sem_fatos_suficientes(monkeypatch, cfg):
    """Lote FTTH de 13/11/2026: o usuário pediu para a checagem de fatos não bloquear (só nessa execução)."""
    _preparar_pipeline(monkeypatch)
    with pytest.raises(_ChegouNoRoteiro):
        pipeline.executar(dict(cfg, _sem_crivo=True))


def test_sem_a_flag_a_checagem_continua_bloqueando(monkeypatch, cfg):
    _preparar_pipeline(monkeypatch)
    with pytest.raises(SystemExit):
        pipeline.executar(cfg)


def test_chave_salva_com_setx_e_lida_do_registro(monkeypatch):
    """Lote FTTH: o processo foi aberto antes do setx e não via PIXABAY_API_KEY (0 fotos no vídeo 1)."""
    from videobot import util
    monkeypatch.delenv("CHAVE_TESTE_X", raising=False)
    monkeypatch.setattr(util.sys, "platform", "win32")

    class K:
        def __enter__(self): return self
        def __exit__(self, *a): return False
    fake = types.SimpleNamespace(HKEY_CURRENT_USER=0, OpenKey=lambda *a: K(), QueryValueEx=lambda k, n: ("segredo", 1))
    monkeypatch.setitem(sys.modules, "winreg", fake)
    assert util.chave("CHAVE_TESTE_X") == "segredo"
    monkeypatch.delenv("CHAVE_TESTE_X", raising=False)


def test_historico_do_pc_fica_fora_do_arquivo_do_github(monkeypatch, tmp_path):
    """O historico/temas.json entrava em conflito no git toda vez que o PC gerava vídeo."""
    monkeypatch.setattr(pipeline, "HIST", tmp_path / "temas.json")
    monkeypatch.setattr(pipeline, "HIST_LOCAL", tmp_path / "temas_local.json")
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    pipeline.registrar_tema({"data": "2026-11-20", "slug": "pc"})
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    pipeline.registrar_tema({"data": "2026-11-21", "slug": "gh"})
    assert [e["slug"] for e in pipeline.ler_json(tmp_path / "temas.json", [])] == ["gh"]
    assert [e["slug"] for e in pipeline.ler_json(tmp_path / "temas_local.json", [])] == ["pc"]
    assert [e["slug"] for e in pipeline.historico()] == ["pc", "gh"], "a escolha de tema enxerga os dois"


def test_sem_crivo_e_proibido_no_github(monkeypatch):
    from videobot import __main__ as m
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    with pytest.raises(SystemExit) as e:
        m.main(["run", "--sem-crivo"])
    assert "não é permitido no GitHub" in str(e.value)


def test_legenda_tiktok_instagram_termina_com_comente():
    """20/11/2026: a legenda saía com 'Comente Sim ou Não!'; agora sempre 'Comente!' (comentário aberto)."""
    from videobot.publish import cta_legenda
    assert cta_legenda("Quantas casas a IA consome por dia? Comente Sim ou Não!") == "Quantas casas a IA consome por dia? Comente!"
    assert cta_legenda("A IA vai te substituir? Responda: sim ou não?") == "A IA vai te substituir? Comente!"
    assert cta_legenda("Isso muda tudo. Comente!") == "Isso muda tudo. Comente!"
    assert cta_legenda("Isso muda tudo.") == "Isso muda tudo. Comente!"
    assert cta_legenda("Sim, a IA já faz isso hoje. Comente sim ou não") == "Sim, a IA já faz isso hoje. Comente!"
