"""Vídeo de Wi-Fi refeito em 23/11: uma ilustração contínua da casa (engine/planta.js) no lugar de cenas soltas.
Pedido: todas as cenas técnicas e ilustradas, ondas perdendo força nas paredes, sem checagem de fatos no diagrama,
unidades brasileiras."""
from __future__ import annotations

import copy
import datetime as dt
import re
from pathlib import Path

import yaml

from videobot import planta, render, script

RAIZ = Path(__file__).resolve().parents[1]
CFG = yaml.safe_load((RAIZ / "config.yml").read_text(encoding="utf-8"))
JS = (RAIZ / "engine" / "planta.js").read_text(encoding="utf-8")


def _cfg(so_planta=True):
    c = copy.deepcopy(CFG)
    c["formato"] = "__"
    c["roteiro"]["so_planta"] = so_planta
    return c


def _cena(i, passo, **prm):
    return {"id": f"s{i}", "text": "O sinal perde força.", "template": "planta", "fact_ids": [], "params": {"passo": passo, "titulo": "x", **prm}}


def _erros(cenas, cfg=None):
    c = cfg or _cfg()
    c["formato"] = "curto"
    r = {"chapters": [{"title": "x", "scenes": cenas}], "thumb": {"lines": [{"text": "x"}]}, "publicacao": {"youtube": {"titulo": "x"}, "tiktok": {"x": 1}}}
    return script.validar(r, {"fatos": []}, c, dt.date(2026, 11, 23))


def test_passos_do_python_e_do_motor_sao_os_mesmos():
    bloco = JS[JS.index("const PASSOS = {"):JS.index("WPL.PASSOS")]
    assert set(re.findall(r"([a-z_]+): \{", bloco)) == set(planta.PASSOS)
    for p in planta.PASSOS:
        assert p in script.TEMPLATES


def test_motor_carrega_a_planta_e_ela_substitui_o_3d():
    assert '<script src="planta.js"></script>' in (RAIZ / "engine" / "index.html").read_text(encoding="utf-8")
    eng = (RAIZ / "engine" / "engine.js").read_text(encoding="utf-8")
    assert "ST.scene3d === 'planta' ? window.WPL" in eng and "T.planta = function" in eng


def test_ondas_perdem_forca_nas_paredes_e_no_mapa_de_calor():
    """As ondas são coloridas pelo sinal em cada ponto (calculado com a perda de cada parede), não um círculo fixo."""
    assert "rssiDe(ap, mx, my, b5)" in JS and "corDe(p," in JS
    assert "PERDA[w[4]]" in JS, "cada parede atravessada tira dB"


def test_no_mesh_nao_aparece_antes_do_passo_mesh():
    """Prévia: o NÓ 2 aparecia na casa vazia porque globalAlpha negativo é ignorado pelo canvas."""
    assert "a = Math.max(0, Math.min(1, a)); if (a <= 0.01) return;" in JS


def test_cenas_da_planta_nao_passam_pela_checagem_de_fatos():
    sc = _cena(1, "paredes", titulo="Alvenaria tira 10 dB", value=-75)
    assert script.numeros_checaveis(sc) == []
    assert script.numeros_checaveis({"template": "topologia", "params": {"nodes": [{"label": "8 km"}]}}) == []


def test_video_so_planta_exige_planta_em_todas_as_cenas_e_variedade_de_passos():
    boas = [_cena(i, p) for i, p in enumerate(["casa", "ondas", "paredes", "obstaculos", "distancia", "zona_morta", "bandas", "mesh", "roaming"])]
    boas.append(_cena(99, "cta", options=["Sim", "Não"]))
    assert not [e for e in _erros(boas) if "planta" in e or "passo" in e]
    mista = boas[:-1] + [{"id": "c", "text": "Comenta!", "template": "cta", "fact_ids": [], "params": {}}]
    assert any("TODAS as cenas" in e for e in _erros(mista))
    pobre = [_cena(i, "ondas") for i in range(8)] + [_cena(9, "cta")]
    assert any("passos diferentes" in e for e in _erros(pobre))
    assert any("inexistentes" in e for e in _erros(boas[:-1] + [_cena(5, "voo_de_drone"), _cena(9, "cta")]))
    assert not [e for e in _erros(mista, _cfg(False)) if "TODAS as cenas" in e], "só vale quando a pauta pede"


def test_cta_da_planta_fica_cordial():
    r = {"chapters": [{"scenes": [_cena(1, "cta", options=["Sim", "Não"])]}]}
    r["chapters"][0]["scenes"][0]["emocao"] = "enfático no número"
    script.emocoes_coerentes(r)
    assert r["chapters"][0]["scenes"][0]["emocao"] == "cordial e direto"


def test_pipeline_sem_foto_quadro_nem_3d_na_ilustracao():
    pipe = (RAIZ / "videobot" / "pipeline.py").read_text(encoding="utf-8")
    assert 'ilustrada = (roteiro.get("cena3d") or cfg["visual"].get("cena3d") or "") == "planta"' in pipe
    assert "creditos = [] if ilustrada else midia.aplicar(" in pipe
    r = {"formato": "curto", "tema": "Wi-Fi", "chapters": [{"title": "x", "scenes": [_cena(1, "ondas")]}]}
    c = copy.deepcopy(CFG); c["visual"]["cena3d"] = "planta"
    narr = {"cenas": {"s1": {"dur": 3, "wav": "", "words": [{"w": "x", "s": 0, "e": 0.3}]}}}
    data = render.montar_timeline(r, narr, c)
    assert data["scene3d"] == "planta" and "_3d" not in data["segments"][0]["params"]


def test_unidades_brasileiras_na_regra_do_roteiro():
    assert "(m, m², km, cm, °C, L, kg)" in (RAIZ / "videobot" / "script.py").read_text(encoding="utf-8")
    sc = {"id": "g", "text": "Cabem cinco galões.", "template": "headline", "fact_ids": [], "params": {"text": "5 galões"}}
    assert any("métricas" in e for e in _erros([sc], _cfg(False)))


# ---------------------------------------------------------------- storyboard do usuário (3D -> 2D -> 3D)
import json

ROT = json.loads((RAIZ / "roteiros" / "2026-11-23_wifi_mesh.json").read_text(encoding="utf-8"))


def test_roteiro_do_storyboard_usa_so_passos_validos_e_casa_3d_com_2d():
    cenas = [sc for ch in ROT["chapters"] for sc in ch["scenes"]]
    passos = [sc["params"]["passo"] for sc in cenas]
    assert all(sc["template"] == "planta" for sc in cenas) and set(passos) <= set(planta.PASSOS)
    assert passos[:4] == ["quarto_problema", "quarto_fraco", "quarto_sem_sinal", "corredor"], "começa no 3D (o problema)"
    assert passos[4] == "transicao" and passos[-2:] == ["cobertura", "quarto_resolvido"], "3D -> planta -> 3D (match cut do celular)"
    assert not any(re.search(r"\d", sc["text"]) for sc in cenas), "narração por extenso"
    assert ROT["cena3d"] == "planta" and ROT["planta"]["nos"] == [[6.4, 3.9]], "um segundo ponto mesh, como no storyboard"
    assert len(ROT["publicacao"]["youtube"]["titulo"]) <= 61


def test_casa_3d_usa_as_mesmas_paredes_da_planta_2d():
    """A transição só casa se o 3D e o 2D forem a mesma casa: o 3D recebe PAREDES e a escala R da planta."""
    js3 = (RAIZ / "engine" / "planta3d.js").read_text(encoding="utf-8")
    assert "PL.PAREDES.forEach" in js3 and "PL.R.s" in js3
    assert "WPL3.init(box, st, { PAREDES, R })" in JS
    assert "const CEL = [9.75, 3.0];" in JS and "const P = V(10.0, 0, 3.0);" in js3, "celular 2D no mesmo lugar da pessoa 3D"
    idx = (RAIZ / "engine" / "index.html").read_text(encoding="utf-8")
    assert idx.index("planta3d.js") < idx.index('src="planta.js"')


def test_sem_modelo_pronto_no_3d():
    js3 = (RAIZ / "engine" / "planta3d.js").read_text(encoding="utf-8")
    assert not re.search(r"GLTFLoader|OBJLoader|\.glb|\.gltf|\.obj['\"]", js3)


def test_pauta_aponta_o_roteiro_fixo_e_o_pipeline_o_usa():
    from videobot import pauta
    c = copy.deepcopy(CFG)
    pauta.aplicar(c, dt.date(2026, 11, 23))
    assert c["tema"]["roteiro_fixo"] == "roteiros/2026-11-23_wifi_mesh.json"
    assert (RAIZ / c["tema"]["roteiro_fixo"]).exists()
    pipe = (RAIZ / "videobot" / "pipeline.py").read_text(encoding="utf-8")
    assert 'elif (cfg.get("tema") or {}).get("roteiro_fixo"):' in pipe


def test_camada_3d_some_nos_passos_2d_mesmo_com_render_em_partes():
    """Run 45226402450: cada parte do render abre outro navegador; a última imagem 3D ficava atrás da planta 2D
    (a pessoa aparecia atrás do mapa). Nos passos 2D a camada 3D é escondida a cada quadro."""
    assert "WPL3.cv.style.visibility = em3d ? 'visible' : 'hidden';" in JS
