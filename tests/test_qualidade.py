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


def test_tags_em_texto_viram_lista():
    """Run #18: o modelo mandou as tags como um texto só e o pacote ficou com 1 tag."""
    from videobot.publish import _lista
    assert _lista("IA, OpenAI, Sam Altman") == ["IA", "OpenAI", "Sam Altman"]
    assert _lista("#ia #tecnologia #openai") == ["#ia", "#tecnologia", "#openai"]
    assert _lista(["a", "b"]) == ["a", "b"] and _lista("") == []


def test_roteiro_curto_pede_palavras_por_cena(cfg):
    """Run #18: com 'frases curtas' o roteiro saiu com 136 palavras (meta 157-197)."""
    fatos = {"tema": "x", "angulo": "", "fatos": []}
    p = script._prompt({"titulo": ""}, fatos, cfg, dt.date(2026, 11, 11), script._alvos(cfg))
    assert "Cada cena tem cerca de" in p and "NÃO significam roteiro curto" in p


def test_catalogo_3d_avisa_que_icone_nao_vale():
    """Run #18: a IA usou nomes de ícone (lock, warning) como objetos 3D."""
    from videobot.objetos3d import prompt_catalogo
    assert "SOMENTE os ids" in prompt_catalogo()


# ---------------------------------------------------------------- vídeo longo (13/11/2026)
def test_longo_usa_roteiro_em_etapas_e_curto_nao(monkeypatch, cfg):
    """O longo é escrito em etapas (estrutura + capítulos); o curto continua com o prompt único."""
    from videobot import script_longo
    chamou = {}
    monkeypatch.setattr(script_longo, "escrever_longo", lambda *a: chamou.update(longo=1) or {
        "tema": "t", "_modelo": "m", "chapters": [{"title": "a", "scenes": [{"id": "x", "text": "oi", "fact_ids": []}]}],
        "thumb": {"lines": [{"text": "x"}]}, "publicacao": {}})
    fatos = {"tema": "t", "fatos": []}
    r = script.escrever({"titulo": ""}, fatos, dict(cfg, formato="longo"), dt.date(2026, 11, 13))
    assert chamou == {"longo": 1} and r["modelo_roteiro"] == "m"


def test_estrutura_longa_pede_gancho_promessa_e_foto_da_thumb(cfg):
    from videobot import script_longo
    c = dict(cfg, formato="longo")
    p = script_longo.prompt_estrutura({"titulo": ""}, {"tema": "t", "fatos": []}, c, dt.date(2026, 11, 13), script._alvos(c))
    assert "primeiros 30 segundos" in p and '"promessa"' in p and '"thumb_foto"' in p and "até 60 caracteres" in p


def test_capitulos_tem_papel_e_orcamento(cfg):
    from videobot import script_longo
    est = {"promessa": "P", "capitulos": [{"title": f"c{i}", "objetivo": "o", "gancho_final": "g"} for i in range(6)]}
    pc = lambda i: script_longo.prompt_capitulo({}, {"tema": "t", "fatos": []}, cfg, dt.date(2026, 11, 13), est, i, 200, "antes")
    assert "GANCHO" in pc(0) and "no máximo 16 palavras" in pc(0)
    assert "FINAL" in pc(5) and "cta" in pc(5)
    assert any('kind \\"subscribe\\"' in pc(i) or 'kind "subscribe"' in pc(i) for i in range(1, 5)), "falta o CTA de inscrição no meio"
    assert "cerca de 200 palavras" in pc(2) and "antes" in pc(2)


@pytest.mark.lento
def test_thumb_com_foto_sai_em_1920_e_abaixo_de_2mb(tmp_path, cfg):
    from PIL import Image
    from conftest import ffmpeg
    from videobot import render
    ffmpeg("-f", "lavfi", "-i", "testsrc2=size=1200x1600", "-frames:v", "1", tmp_path / "f.jpg")
    info = {"lines": [{"text": "A OPENAI"}, {"text": "ACELEROU", "hl": True}], "number": "US$ 500 bi", "numberLabel": "em valor",
            "photo": (tmp_path / "f.jpg").resolve().as_uri()}
    hq, pq = render.thumbs(info, cfg, tmp_path, False)
    assert Image.open(hq).size == (1920, 1080) and hq.stat().st_size < 2_000_000
    assert Image.open(pq).size == (1280, 720)


def test_publicacao_com_chaves_achatadas_vira_normal():
    """Run #23: o modelo devolveu {"youtube": {"youtube.abertura": ...}} e o vídeo saiu sem título nem abertura."""
    from videobot.publish import normalizar_publicacao
    r = {"tema": "t", "chapters": [{"scenes": [{"text": "oi"}]}]}
    p = normalizar_publicacao({"youtube": {"youtube.abertura": "A", "titulo": "T"}, "youtube.tags": "a, b"}, r)
    assert (p["youtube"]["abertura"], p["youtube"]["titulo"], p["youtube"]["tags"]) == ("A", "T", ["a", "b"])


def test_embalagem_do_longo_preenche_titulo_alternativos_e_thumb(monkeypatch, cfg):
    from videobot import script_longo
    monkeypatch.setattr(script_longo, "gerar_json", lambda *a, **k: ({
        "titulo": "Data centers já gastam 415 TWh", "alternativos": ["A", "B", "C" * 80],
        "thumb": {"lines": [{"text": "SUA CONTA"}, {"text": "SOBE", "hl": True}], "number": "415"},
        "thumb_foto": "power plant cooling towers"}, {}, "m"))
    r = script_longo.embalar({"tema": "t", "chapters": [{"title": "c", "scenes": [{"text": "x"}]}], "publicacao": {}}, {"fatos": []}, cfg)
    yt = r["publicacao"]["youtube"]
    assert yt["titulo"] == "Data centers já gastam 415 TWh" and yt["alternativos"] == ["A", "B"]
    assert r["thumb"]["lines"][0]["text"] == "SUA CONTA" and r["thumb_foto"] == "power plant cooling towers"


def test_visao_tenta_cada_modelo_uma_vez(monkeypatch, cfg):
    """Run #23: 3 tentativas x 5 modelos x esperas = 35 min presos na mídia."""
    from videobot import llm
    monkeypatch.setattr(llm, "chave", lambda n: "x")
    monkeypatch.setattr(llm, "_modelos_visao", lambda: ["a:free", "b:free", "c:free"])
    chamadas = []
    monkeypatch.setattr(llm, "_openai", lambda prov, m, *a: chamadas.append(m) or (429, "", 0.0, "Provider returned error"))
    with pytest.raises(RuntimeError):
        llm.gerar_visao_json("p", ["data:image/jpeg;base64,x"], dict(cfg, llm=dict(cfg["llm"], visao={"modelos": ["a", "b", "c"]})))
    assert chamadas == ["a:free", "b:free", "c:free"]


def test_sem_visao_escolhe_so_entre_pixabay_pelas_tags(monkeypatch, cfg):
    from videobot import llm, midia
    vistos = []
    monkeypatch.setattr(llm, "gerar_json", lambda p, *a, **k: vistos.append(p) or ({"escolha": 0}, {}, "m"))
    cands = [{"fonte": "Wikimedia Commons", "tipo": "foto", "titulo": "x", "descricao": "", "categorias": [], "url": "u1"},
             {"fonte": "Pixabay", "tipo": "foto", "titulo": "factory, robot", "descricao": "", "categorias": ["factory"], "url": "u2"}]
    k = midia.escolher({"id": "s", "text": "robôs na fábrica"}, cands, dict(cfg, midia=dict(cfg["midia"], visao=False)))
    assert k == 1 and "Commons" not in vistos[0] and "factory, robot" in vistos[0]
