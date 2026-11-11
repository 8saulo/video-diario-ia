"""Regressões do salto de qualidade (11/11/2026): narração dirigida no roteiro e 3D com modelos prontos."""
from __future__ import annotations

import datetime as dt
import json

import pytest

from videobot import script, util


def test_conversor_de_modulo_three_vira_script_global():
    """Os extras do Three.js são módulos ES; o motor abre em file:// e precisa deles como script comum."""
    src = ("import { Mesh, Vector3 as V3 } from 'three';\n"
           "import { toTrianglesDrawMode } from '../utils/BufferGeometryUtils.js';\n"
           "export function ajuda() { return 1; }\n"
           "class Loader {}\n"
           "export { Loader };\n")
    out = util.modulo_para_script(src)
    assert "const { Mesh, Vector3: V3 } = THREE;" in out
    assert "const { toTrianglesDrawMode } = window.THREEX;" in out
    assert "\nfunction ajuda()" in out
    assert "Object.assign(window.THREEX, { ajuda, Loader });" in out
    assert "export" not in out.replace("exportados", "")
    assert "\x01" not in out, "a referência \\1 do re.sub virou caractere de controle"


def test_conversor_recusa_import_que_nao_entende():
    with pytest.raises(ValueError):
        util.modulo_para_script("import * as X from 'three';\n")


def test_roteiro_pede_emocao_por_cena_e_tom_falado(cfg):
    fatos = {"tema": "Robôs", "angulo": "", "fatos": [{"id": 1, "afirmacao": "x", "numeros": [], "fonte": "f", "data": ""}]}
    p = script._prompt({"titulo": ""}, fatos, cfg, dt.date(2026, 11, 11), script._alvos(cfg))
    assert '"emocao"' in p and "DIREÇÃO DE VOZ" in p
    assert "frases curtas (até 12 palavras)" in p


@pytest.mark.lento
def test_motor_3d_carrega_robo_pronto_e_lupa_sem_erro_js(cfg):
    """O robô vem do GLB (CC0) com animação; nenhum erro de JavaScript ao montar e desenhar."""
    from videobot import render
    util.garantir_gsap()
    seg = lambda i, objs: {"id": f"s{i}", "kind": "scene", "template": "headline", "start": i * 3.0, "dur": 3.0,
                           "text": "x", "params": {"text": "x", "_3d": {"objetos": objs, "camera": "orbita"}}}
    data = {"w": 1080, "h": 1920, "fps": 30, "duration": 6, "captions": [], "showCaptions": False, "brand": "",
            "brandLogo": "", "brandLogoOpacity": 0, "brandLogoPeriod": 9, "scene3d": "tema", "scale3d": 0.5,
            "theme": render._tema(cfg["visual"]), "segments": [seg(0, ["robo"]), seg(1, ["lupa"])]}
    pw, br, pg = render._abrir(1080, 1920)
    erros = []
    pg.on("pageerror", lambda e: erros.append(str(e)))
    try:
        render._boot(pg, data)
        for t in (0.5, 1.5, 3.5):
            pg.evaluate("t => window.renderAt(t)", t)
        assert pg.evaluate("() => !!window.W3T._modelos.robo && window.W3T._modelos.robo.animations.length > 5")
    finally:
        br.close(); pw.stop()
    assert not erros, erros
