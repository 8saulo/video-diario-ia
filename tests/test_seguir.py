"""Cena final de seguir/se inscrever (20/11/2026: todo vídeo termina pedindo para seguir no YouTube, Instagram e TikTok)."""
from __future__ import annotations

import copy

import numpy as np
import pytest

from videobot import audio, publish, render


def _roteiro(formato="curto"):
    return {"formato": formato, "tema": "t", "cena3d": "gpon", "chapters": [
        {"title": "A", "scenes": [{"id": "a", "text": "um dois", "params": {}}]},
        {"title": "B", "scenes": [{"id": "b", "text": "tres quatro", "params": {}}]}]}


def _narr():
    pal = [{"w": "x", "s": 0.1, "e": 0.4}, {"w": "y", "s": 0.5, "e": 0.9}]
    return {"cenas": {"a": {"dur": 1.0, "wav": "", "words": pal}, "b": {"dur": 1.0, "wav": "", "words": pal}}}


@pytest.mark.parametrize("formato", ["curto", "longo"])
def test_todo_video_termina_com_a_cena_de_seguir(cfg, formato):
    """Curto e longo: o último segmento é a cena de seguir com YouTube, Instagram e TikTok, depois de toda a narração."""
    data = render.montar_timeline(_roteiro(formato), _narr(), cfg)
    fim = data["segments"][-1]
    assert fim["kind"] == "seguir"
    assert [r["rede"] for r in fim["redes"]] == ["youtube", "instagram", "tiktok"]
    assert all(r["svg"].startswith("file:") for r in fim["redes"]), "logos oficiais vêm de assets/redes"
    anterior = data["segments"][-2]
    assert fim["start"] >= anterior["start"] + anterior["dur"] - 1e-6
    assert abs(data["duration"] - (fim["start"] + fim["dur"])) < 1e-3
    assert len(fim["taps"]) == 3 and max(fim["taps"]) < fim["dur"] - 1, "os 3 toques acontecem antes do fim da cena"
    assert not [c for c in data["captions"] if c["end"] > fim["start"] + 1e-3], "sem legenda em cima da cena final"


def test_cena_de_seguir_pode_ser_desligada(cfg):
    c = copy.deepcopy(cfg)
    c["visual"]["final_seguir"] = {"ativo": False}
    data = render.montar_timeline(_roteiro(), _narr(), c)
    assert data["segments"][-1]["kind"] == "scene"


def test_perfis_aparecem_quando_configurados(cfg):
    c = copy.deepcopy(cfg)
    c["visual"]["final_seguir"] = {"perfis": {"instagram": "@canal"}}
    fim = render.final_seguir(c, 0, False)
    assert {r["rede"]: r["perfil"] for r in fim["redes"]}["instagram"] == "@canal"


def test_publicacao_aceita_a_cena_de_seguir(cfg):
    """capitulos() e corte_tiktok() percorrem os segmentos; a cena final (sem texto) não pode quebrar o pacote."""
    data = render.montar_timeline(_roteiro("longo"), _narr(), cfg)
    assert publish.capitulos(data, _roteiro("longo"))
    publish.corte_tiktok(data, _roteiro("longo"))


def test_mixer_poe_um_clique_em_cada_toque(cfg, tmp_path, monkeypatch):
    """Os cliques do áudio caem nos mesmos tempos em que o dedo toca os botões no vídeo."""
    capt = {}
    monkeypatch.setattr(audio, "loudnorm", lambda a, b, **k: b.write_bytes(a.read_bytes()))
    monkeypatch.setattr(audio, "medir", lambda p: {"mean_volume": 0, "max_volume": 0, "lufs": 0, "true_peak": 0})
    orig = audio.escrever_wav
    monkeypatch.setattr(audio, "escrever_wav", lambda p, x, canais=1: (capt.setdefault("x", x), orig(p, x, canais)))
    c = copy.deepcopy(cfg)
    c["visual"]["musica"] = False
    seg = {"kind": "seguir", "start": 1.0, "dur": 4.0, "taps": [1.25, 1.8, 2.35], "params": {}}
    audio.mixar([seg], 5.0, tmp_path, c)
    x = np.abs(capt["x"])
    for tp in seg["taps"]:
        j = int((1.0 + tp) * audio.SR)
        assert x[j:j + 2000].max() > 0.05


@pytest.mark.lento
def test_motor_desenha_a_cena_de_seguir_e_marca_os_botoes(cfg):
    """No fim da cena os 3 botões mostram INSCRITO/SEGUINDO, sem erro de página nem alerta de layout."""
    from videobot import util
    util.garantir_gsap()
    fim = render.final_seguir(cfg, 0.0, False)
    data = {"w": 1080, "h": 1920, "fps": 30, "duration": fim["dur"], "captions": [], "showCaptions": False, "brand": "",
            "brandLogoPeriod": 9, "scene3d": "tema", "scale3d": 0.5, "theme": render._tema(cfg["visual"]), "segments": [fim]}
    pw, br, pg = render._abrir(1080, 1920)
    erros = []
    pg.on("pageerror", lambda e: erros.append(str(e)))
    try:
        render._boot(pg, data)
        pg.evaluate("t => window.renderAt(t)", 0.6)
        antes = pg.evaluate("() => [...document.querySelectorAll('.fim-feito')].map(e => getComputedStyle(e).visibility)")
        pg.evaluate("t => window.renderAt(t)", fim["dur"] - 0.2)
        depois = pg.evaluate("() => [...document.querySelectorAll('.fim-feito')].map(e => getComputedStyle(e).visibility)")
        alertas = pg.evaluate("() => window.audit()")
    finally:
        br.close(); pw.stop()
    assert not erros, erros
    assert antes == ["hidden"] * 3 and depois == ["visible"] * 3
    assert not alertas, alertas
