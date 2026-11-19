"""Regressões do quadro de dossiê e da narrativa (19/11/2026)."""
from __future__ import annotations

import datetime as dt

import pytest

from videobot import elementos, script


def test_slug_do_simple_icons():
    assert elementos.slug_simple_icons("NVIDIA") == "nvidia"
    assert elementos.slug_simple_icons("Dolby+") == "dolbyplus"
    assert elementos.slug_simple_icons("Node.js") == "nodedotjs"


def test_pagina_da_wikipedia_tem_que_ser_da_pessoa():
    """'Kimberly Powell' redireciona para 'Jensen Huang spying scandal': a foto seria do Jensen."""
    assert not elementos._mesma_pessoa("Kimberly Powell", "Jensen Huang spying scandal")
    assert elementos._mesma_pessoa("Jensen Huang", "Jensen Huang")
    assert elementos._mesma_pessoa("Lula", "Luiz Inácio Lula da Silva")


def test_montar_poe_pessoa_logo_e_midia_como_recortes(monkeypatch, tmp_path, cfg):
    from videobot import llm
    monkeypatch.setattr(llm, "gerar_json", lambda *a, **k: ({"cenas": [
        {"id": "a", "pessoas": [{"nome": "Jensen Huang", "wiki": "Jensen Huang", "papel": "CEO · NVIDIA"}], "marcas": ["NVIDIA"],
         "manchete": "Chips sob investigação", "nota": {"valor": "US$ 5 tri", "rotulo": "valor"}, "carimbo": "suposta espiã",
         "etiqueta": "dossiê · caso nvda", "destaque": "Jensen Huang"},
        {"id": "b", "pessoas": [], "marcas": [], "manchete": "", "carimbo": "", "etiqueta": ""}]}, {}, "m"))
    monkeypatch.setattr(elementos, "foto_pessoa", lambda n, w, p: {"src": "file:///j.jpg", "credito": "Foto: X / Wikimedia Commons (CC BY 4.0)", "pagina": "p", "nome": n})
    monkeypatch.setattr(elementos, "logo", lambda n, p: {"svg": "file:///n.svg", "cor": "#76B900", "nome": "NVIDIA"})
    rot = {"tema": "t", "chapters": [{"scenes": [
        {"id": "a", "text": "x", "params": {"_photo": "file:///f.jpg", "_credit": "Foto: Y"}},
        {"id": "b", "text": "y", "params": {}}]}]}
    cred = elementos.montar(rot, cfg, tmp_path)
    a, b = rot["chapters"][0]["scenes"]
    q = a["params"]["_quadro"]
    tipos = [i["tipo"] for i in q["itens"]]
    assert tipos[:3] == ["pessoa", "logo", "foto"] and len(tipos) == 4, "no máximo 4 recortes por cena"
    assert "_photo" not in a["params"], "a foto vira recorte e deixa de ocupar a tela inteira"
    assert q["carimbo"] == "SUPOSTA ESPIÃ" and q["itens"][0].get("destaque")
    assert "_quadro" not in b["params"], "cena sem nada fica com o fallback (3D)"
    assert cred and cred[0]["titulo"] == "Jensen Huang"


def test_roteiro_curto_pede_narrativa_e_gancho_curto(cfg):
    fatos = {"tema": "t", "angulo": "", "fatos": []}
    p = script._prompt({"titulo": ""}, fatos, cfg, dt.date(2026, 11, 19), script._alvos(cfg))
    assert "NARRATIVA" in p and "não uma lista de manchetes" in p and "no máximo 9 palavras" in p


def test_gancho_longo_demais_e_apontado(cfg):
    r = {"chapters": [{"title": "x", "scenes": [{"id": "a", "text": " ".join(["palavra"] * 15), "template": "headline", "params": {}}]}],
         "thumb": {"lines": [{"text": "x"}]}, "publicacao": {"youtube": {"titulo": "t"}, "tiktok": {"x": 1}}}
    err = script.validar(r, {"fatos": []}, cfg, dt.date(2026, 11, 19))
    assert any("gancho" in e for e in err)


@pytest.mark.lento
def test_motor_monta_o_quadro_sem_erro_e_desliga_o_3d(tmp_path, cfg):
    from PIL import Image
    from videobot import render, util
    util.garantir_gsap()
    Image.new("RGB", (400, 300), (200, 30, 30)).save(tmp_path / "f.jpg")
    (tmp_path / "l.svg").write_text("<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'><circle cx='12' cy='12' r='10'/></svg>", encoding="utf-8")
    u = lambda n: (tmp_path / n).resolve().as_uri()
    q = {"itens": [{"tipo": "pessoa", "src": u("f.jpg"), "nome": "Fulano", "papel": "CEO", "credito": "Foto: X", "destaque": True},
                   {"tipo": "logo", "svg": u("l.svg"), "cor": "#76B900", "nome": "Marca"},
                   {"tipo": "manchete", "texto": "Manchete de teste"}, {"tipo": "nota", "valor": "10x", "rotulo": "mais rápido"}],
         "carimbo": "CONFIRMADO", "etiqueta": "DOSSIÊ · TESTE"}
    seg = {"id": "s0", "kind": "scene", "template": "headline", "start": 0, "dur": 3.0, "text": "x",
           "params": {"text": "x", "_quadro": q, "_3d": {"objetos": ["lupa"], "camera": "orbita"}}}
    data = {"w": 1080, "h": 1920, "fps": 30, "duration": 3, "captions": [], "showCaptions": False, "brand": "", "brandLogo": "",
            "brandLogoOpacity": 0, "brandLogoPeriod": 9, "scene3d": "tema", "scale3d": 0.5, "theme": render._tema(cfg["visual"]), "segments": [seg]}
    pw, br, pg = render._abrir(1080, 1920)
    erros = []
    pg.on("pageerror", lambda e: erros.append(str(e)))
    try:
        render._boot(pg, data)
        pg.evaluate("t => window.renderAt(t)", 1.5)
        assert pg.evaluate("() => document.querySelectorAll('.q-card').length") == 4
        assert pg.evaluate("() => document.querySelector('.q-carimbo').textContent") == "CONFIRMADO"
        assert pg.evaluate("() => document.getElementById('gl3d').style.visibility") == "hidden"
        assert pg.evaluate("() => document.getElementById('stage').classList.contains('mode-quadro')")
    finally:
        br.close(); pw.stop()
    assert not erros, erros
