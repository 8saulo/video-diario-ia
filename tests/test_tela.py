"""O que aparece na tela tem que bater com a fala (longo de 21/11, deepfakes): escala dos números, casas decimais,
título de capítulo inteiro, etiquetas do quadro longe da legenda, mídia do Pixabay e refazer o vídeo sem IA."""
from __future__ import annotations

import json

import pytest

from videobot import midia, render, rerender


@pytest.mark.parametrize("valor,suf,esperado", [
    (14000, " mi", (14, " mil")),          # "14.000 mi" = 14 bilhões na tela; a fala dizia quatorze mil
    (8000000, " mi", (8, " mi")),          # "8.000.000 mi"
    (500000, " mi", (500, " mil")),
    (14678, " mil", (14.7, " mil")),
    (1290000000, "bi", (1.3, " bi")),
    (547, " mi", (547, " mi")),            # já está na escala certa: não mexe
    (2137, "%", (2137, "%")),              # porcentagem não é escala
])
def test_numero_com_escala_por_extenso_e_reescalado(valor, suf, esperado):
    out = render.corrigir_numeros({"value": valor, "suffix": suf, "label": "x"})
    assert (out["value"], out["suffix"]) == esperado


def test_correcao_vale_dentro_do_compare_e_das_listas():
    p = {"left": {"value": 8000000, "suffix": " mi"}, "right": {"value": 500000, "suffix": " mi"},
         "items": [{"value": 0.03, "suffix": "%"}, {"value": True, "suffix": " mi"}]}
    out = render.corrigir_numeros(p)
    assert (out["left"]["value"], out["left"]["suffix"]) == (8, " mi")
    assert (out["right"]["value"], out["right"]["suffix"]) == (500, " mil")
    assert out["items"][0] == {"value": 0.03, "suffix": "%"} and out["items"][1]["value"] is True


def test_linha_do_tempo_ja_sai_com_numeros_corrigidos():
    """Curto e longo passam por montar_timeline: o motor nunca recebe 14000 + ' mi'."""
    pal = [{"w": "x", "s": 0.1, "e": 0.4}]
    rot = {"formato": "curto", "tema": "t", "cena3d": "gpon", "chapters": [{"title": "A", "scenes": [
        {"id": "a", "text": "quatorze mil", "template": "bignumber", "params": {"value": 14000, "suffix": " mi"}}]}]}
    cfg = {"visual": {"final_seguir": {"ativo": False}}, "tema": {"nicho": ""}}
    data = render.montar_timeline(rot, {"cenas": {"a": {"dur": 1.0, "wav": "", "words": pal}}}, cfg)
    p = data["segments"][0]["params"]
    assert (p["value"], p["suffix"]) == (14, " mil")


def test_pipeline_corrige_numeros_antes_da_direcao_de_arte():
    """O número 3D (elementos.preparar_3d) sai do roteiro: a correção tem que vir antes, no pipeline."""
    from pathlib import Path
    src = (Path(__file__).resolve().parents[1] / "videobot" / "pipeline.py").read_text(encoding="utf-8")
    assert src.index("render.corrigir_numeros") < src.index('etapa("midia"')


def test_motor_usa_as_casas_do_valor_e_capitulo_ocupa_a_tela():
    """0,03% virava 0% (decimals padrão 0) e o título do capítulo encolhia ao lado do número no modo quadro."""
    from pathlib import Path
    js = (Path(__file__).resolve().parents[1] / "engine" / "engine.js").read_text(encoding="utf-8")
    assert "p.decimals != null ? p.decimals" in js
    assert "seg.kind === 'chapter' && !ST.port" in js
    q = (Path(__file__).resolve().parents[1] / "engine" / "quadro.js").read_text(encoding="utf-8")
    assert "R.y + R.h + 10" not in q, "as etiquetas do quadro horizontal não podem ir para baixo, onde fica a legenda"


def test_remapear_troca_caminhos_do_github_pelos_locais(tmp_path):
    pasta = tmp_path / "2026-11-21_x"
    pasta.mkdir()
    velho = "/home/runner/work/video-diario-ia/video-diario-ia"
    txt = json.dumps({"a": f"file://{velho}/saida/2026-11-21_x/midia/q/", "b": f"{velho}/saida/2026-11-21_x/audio/c.wav",
                      "logo": f"file://{velho}/assets/logo.png"})
    out = json.loads(rerender.remapear(txt, pasta, raiz=tmp_path))
    assert out["a"] == (pasta / "midia" / "q").resolve().as_uri() + "/"
    assert out["b"] == (pasta / "audio" / "c.wav").resolve().as_posix()
    assert out["logo"] == (tmp_path / "assets" / "logo.png").resolve().as_uri()


def test_refazer_sem_ia_corrige_numero_e_refaz_o_3d(tmp_path, monkeypatch):
    """rerender: não chama IA nem voz; conserta o número e reextruda o texto 3D com o valor certo."""
    import videobot.texto3d as t3
    monkeypatch.setattr(t3, "svg_de_texto", lambda s: f"<svg>{s}</svg>")
    import videobot.llm as llm
    monkeypatch.setattr(llm, "gerar", lambda *a, **k: (_ for _ in ()).throw(AssertionError("chamou IA")))
    pasta = tmp_path / "2026-11-21_x"
    pasta.mkdir()
    seg = {"id": "q", "kind": "scene", "template": "bignumber", "start": 0, "dur": 2,
           "params": {"value": 14000, "suffix": " mi", "label": "v", "_3d": {"objetos": [{"svg": "<svg>14.000 MI</svg>", "texto": True}]}}}
    (pasta / "timeline.json").write_text(json.dumps({"segments": [seg, {"id": "c", "kind": "chapter"}]}), encoding="utf-8")
    data = rerender.preparar(pasta)
    p = data["segments"][0]["params"]
    assert (p["value"], p["suffix"]) == (14, " mil")
    assert p["_3d"]["objetos"][0]["svg"] == "<svg>14 MIL</svg>"


def test_rerender_tem_comando_na_linha_de_comando(monkeypatch, tmp_path):
    from videobot import __main__ as cli
    chamado = {}
    monkeypatch.setattr(rerender, "refazer_imagem", lambda p, v=None: chamado.update(p=p, v=v))
    cli.main(["rerender", str(tmp_path)])
    assert chamado["p"] == tmp_path and chamado["v"] is None


def test_pixabay_espera_o_limite_em_vez_de_perder_a_midia(monkeypatch):
    """429 do Pixabay derrubava a busca (20 de 36 cenas ficaram sem mídia real); agora espera e tenta de novo."""
    respostas = [429, 200]
    dormiu = []

    class R:
        def __init__(self, st):
            self.status_code, self.headers = st, ({"X-RateLimit-Reset": "7"} if st == 429 else {})

        def raise_for_status(self):
            if self.status_code >= 400:
                raise AssertionError("não devia levantar")

        def json(self):
            return {"hits": [1]}

    monkeypatch.setattr(midia.requests, "get", lambda *a, **k: R(respostas.pop(0)))
    assert midia._get_pixabay("u", {}, dormir=dormiu.append) == {"hits": [1]}
    assert 7.0 in dormiu


@pytest.mark.lento
def test_motor_capitulo_inteiro_decimal_e_etiquetas_longe_da_legenda(cfg):
    """Render real (16:9, modo quadro): título do capítulo sem corte, 0,03% na tela e '// DOSSIÊ' acima do quadro."""
    from videobot import util
    util.garantir_gsap()
    q = {"itens": [{"tipo": "manchete", "texto": "Manchete de teste"}], "etiqueta": "DOSSIÊ · TESTE"}
    segs = [{"id": "s0", "kind": "scene", "template": "headline", "start": 0, "dur": 2, "text": "x",
             "params": {"text": "Oi", "_quadro": q}},
            {"id": "cap5", "kind": "chapter", "start": 2, "dur": 2.2, "num": 5, "total": 7, "title": "Ferramentas reais"},
            {"id": "b", "kind": "scene", "template": "bignumber", "start": 4.2, "dur": 2, "text": "x",
             "params": {"label": "Precisão", "value": 0.03, "suffix": "%"}}]
    data = {"w": 1920, "h": 1080, "fps": 30, "duration": 6.2, "captions": [{"start": 0, "end": 2, "words": [{"w": "legenda", "s": 0}]}],
            "showCaptions": True, "brand": "", "brandLogoPeriod": 9, "scene3d": "", "scale3d": 0.5,
            "theme": render._tema(cfg["visual"]), "segments": segs}
    pw, br, pg = render._abrir(1920, 1080)
    try:
        render._boot(pg, data)
        pg.evaluate("t => window.renderAt(t)", 1.5)
        et = pg.evaluate("() => { const r = document.querySelector('.q-etiqueta').getBoundingClientRect(); return [r.top, r.bottom] }")
        pg.evaluate("t => window.renderAt(t)", 4.0)
        cortado = pg.evaluate("() => [...document.querySelectorAll('.h1')].filter(h => h.offsetParent && h.scrollWidth > h.clientWidth + 1).length")
        pg.evaluate("t => window.renderAt(t)", 6.0)
        num = pg.evaluate("() => [...document.querySelectorAll('.num .n')].map(e => e.textContent)")
    finally:
        br.close(); pw.stop()
    assert et[1] < 200, f"etiqueta do quadro tem que ficar no alto (legenda fica em ~868px): {et}"
    assert cortado == 0
    assert "0,03" in num, num
