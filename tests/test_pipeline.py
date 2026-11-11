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
