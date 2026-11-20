"""Regressões da trilha real (Openverse) e dos efeitos sincronizados com o quadro (20/11/2026)."""
from __future__ import annotations

import numpy as np

from videobot import audio, musica


def test_trilha_so_instrumental_licenca_livre_e_duracao_util(monkeypatch):
    class R:
        def raise_for_status(self): pass
        def json(self):
            return {"results": [
                {"title": "Electro Vocal Mix", "duration": 200000, "url": "u1", "license": "by"},
                {"title": "Tiny jingle", "duration": 20000, "url": "u2", "license": "by"},
                {"title": "Ambient Voyager", "duration": 235000, "url": "u3", "license": "by", "license_version": "3.0", "source": "jamendo"}]}
    monkeypatch.setattr(musica.requests, "get", lambda *a, **k: R())
    cs = musica.candidatos("ambient")
    assert [c["url"] for c in cs] == ["u3"] and cs[0]["licenca"] == "CC BY 3.0"


def test_musica_em_loop_cobre_o_video_no_nivel_da_trilha(tmp_path):
    x = (np.sin(np.linspace(0, 2000, 44100 * 30)) * 0.5).astype(np.float32)
    audio.escrever_wav(tmp_path / "m.wav", x)
    y = audio.musica_em_loop(tmp_path / "m.wav", 44100 * 70)
    assert len(y) == 44100 * 70 and abs(float(np.sqrt((y ** 2).mean())) - 0.06) < 0.01


def test_efeitos_entram_no_tempo_do_quadro(monkeypatch, tmp_path, cfg):
    """Toc de alfinete a cada recorte e batida do carimbo, no ritmo das animações."""
    capturado = {}
    monkeypatch.setattr(audio, "loudnorm", lambda a, b: capturado.setdefault("bruto", a))
    monkeypatch.setattr(audio, "medir", lambda p: {"mean_volume": -16, "max_volume": -2, "lufs": -14, "true_peak": -1})
    seg = {"id": "s", "kind": "scene", "start": 1.0, "dur": 3.0, "params": {"_quadro": {"itens": [{}, {}], "carimbo": "OK"}}}
    cfg = dict(cfg, visual=dict(cfg["visual"], musica=False))
    audio.mixar([seg], 5.0, tmp_path, cfg)
    y = audio.ler_wav(capturado["bruto"])
    t = lambda s: int(s * 44100)
    assert np.abs(y[t(1.50):t(1.60)]).max() > 0.01, "toc do primeiro alfinete"
    assert np.abs(y[t(2.17):t(2.30)]).max() > 0.05, "batida do carimbo"
