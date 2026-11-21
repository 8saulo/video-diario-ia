"""Refaz só a imagem de um vídeo já gerado, sem IA e sem voz nova.

Usa a linha do tempo gravada (timeline.json: cenas, recortes, fotos e tempos), as mídias da pasta e o áudio
do vídeo antigo (narração + trilha + efeitos já mixados). Como os tempos não mudam, o áudio continua sincronizado.
Serve para aplicar correções do motor (layout, números, legendas) num vídeo que já saiu.

  python -m videobot rerender <pasta do vídeo> [--video arquivo.mp4]
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from .util import RAIZ, log, run


def remapear(texto: str, pasta: Path, raiz: Path = RAIZ) -> str:
    """Troca os caminhos da máquina que gerou (ex.: /home/runner/.../video-diario-ia) pelos desta máquina:
    saida/<pasta do vídeo> → a pasta informada; o resto do projeto (assets/...) → a raiz local."""
    m = re.search(r'(?:file://)?(/[^"]*?)/saida/' + re.escape(pasta.name), texto)
    if not m:
        return texto
    velha = m.group(1)
    for antigo, novo in ((f"{velha}/saida/{pasta.name}", pasta.resolve()), (velha, raiz.resolve())):
        texto = texto.replace("file://" + antigo, novo.as_uri()).replace(antigo, novo.as_posix())
    return texto


def preparar(pasta: Path) -> dict:
    """timeline.json da pasta com caminhos locais e os números corrigidos (mesma regra das gerações novas)."""
    from .elementos import _numero_da_cena
    from .render import corrigir_numeros
    from .texto3d import svg_de_texto
    data = json.loads(remapear((pasta / "timeline.json").read_text(encoding="utf-8"), pasta))
    for s in data.get("segments", []):
        if s.get("kind") != "scene":
            continue
        antes = s.get("params") or {}
        s["params"] = novo = corrigir_numeros(antes)
        if novo == antes:
            continue
        # o número em 3D foi extrudado do valor errado: refaz o SVG com o número consertado
        txt = _numero_da_cena({k: v for k, v in novo.items() if not k.startswith("_")})
        for o in ((novo.get("_3d") or {}).get("objetos") or []):
            if isinstance(o, dict) and o.get("texto") and o.get("svg") and txt:
                svg = svg_de_texto(txt)
                if svg:
                    o["svg"] = svg
    return data


def refazer_imagem(pasta: Path, video: Path | None = None) -> Path:
    from . import render
    pasta = Path(pasta)
    if video is None:
        cands = sorted(p for p in pasta.glob("*.mp4") if "previa" not in p.name and not p.stem.endswith("_v2"))
        if not cands:
            raise SystemExit(f"rerender: não achei o vídeo antigo (.mp4) em {pasta}")
        video = cands[0]
    data = preparar(pasta)
    audio = pasta / "_audio_original.wav"
    run(["ffmpeg", "-v", "error", "-y", "-i", video, "-vn", "-ac", "2", "-ar", "44100", "-c:a", "pcm_s16le", audio])
    alertas = render.previa(data, pasta)
    log(f"rerender: CRIVO 5 com {len(alertas)} alerta(s) de layout"
        + (": " + "; ".join(f"{i['seg']}:{i['tipo']}" for i in alertas[:12]) if alertas else ""))
    out = render.render(data, audio, pasta, video.stem + "_v2.mp4")
    audio.unlink(missing_ok=True)
    log(f"rerender: pronto -> {out}")
    return out
