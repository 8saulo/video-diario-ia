"""Texto em 3D gerado por código: contorno das letras da fonte do projeto (Anton, OFL) vira SVG, que o motor extruda.

Nada de modelo pronto: o número ou a palavra-chave de cada cena ("17%", "US$ 5 TRI") vira um objeto 3D com chanfro.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from .util import ENGINE

FONTE = ENGINE.parent / "fonts" / "anton_Anton-Regular.ttf"


@lru_cache(maxsize=2)
def _fonte():
    from fontTools.ttLib import TTFont
    return TTFont(str(FONTE))


def svg_de_texto(texto: str, espaco: float = 0.06) -> str | None:
    """SVG (viewBox em unidades da fonte) com o contorno de cada letra; None se o texto ficar vazio."""
    from fontTools.pens.svgPathPen import SVGPathPen
    from fontTools.pens.transformPen import TransformPen
    texto = (texto or "").strip()[:14]
    if not texto:
        return None
    f = _fonte()
    cmap, gs = f.getBestCmap(), f.getGlyphSet()
    upm = f["head"].unitsPerEm
    asc = f["hhea"].ascent
    x, caminhos = 0.0, []
    for ch in texto:
        nome = cmap.get(ord(ch)) or cmap.get(ord(ch.upper()))
        if not nome:
            x += upm * 0.3
            continue
        g = gs[nome]
        pen = SVGPathPen(gs)
        # SVG tem y para baixo; a fonte, para cima: inverte e desloca pela altura
        g.draw(TransformPen(pen, (1, 0, 0, -1, x, asc)))
        d = pen.getCommands()
        if d:
            caminhos.append(d)
        x += g.width + upm * espaco
    if not caminhos:
        return None
    alt = asc - f["hhea"].descent
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {int(x)} {int(alt)}">'
            + "".join(f'<path d="{d}"/>' for d in caminhos) + "</svg>")
