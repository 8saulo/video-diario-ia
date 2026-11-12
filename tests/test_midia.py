"""Regressões de fotos/vídeos reais, relevância dos objetos 3D e velocidade do render (12/11/2026)."""
from __future__ import annotations

import pytest
from conftest import ffmpeg

from videobot import midia, objetos3d


@pytest.mark.parametrize("lic,ok", [("cc0", True), ("pd", True), ("cc-by-4.0", True), ("cc-by-sa-3.0", True), ("by-sa", True),
                                    ("cc-by-nc-2.0", False), ("cc-by-nd-4.0", False), ("by-nc-sa", False), ("GFDL", False), ("", False)])
def test_so_licencas_com_uso_comercial_e_edicao(lic, ok):
    assert midia.licenca_ok(lic) is ok


def test_filtro_descarta_grafico_png_e_ilustracao():
    """Run de teste: a escolha só pelo título pegou 'Mental Health Statistics ... .png' (um gráfico)."""
    foto = {"tipo": "foto", "titulo": "Robot arm in factory.jpg", "url": "https://x/a.jpg"}
    assert midia.serve(foto)
    assert not midia.serve({**foto, "url": "https://x/a.png"})
    assert not midia.serve({**foto, "titulo": "Statistics of workers chart"})
    assert not midia.serve({**foto, "titulo": "Generative AI illustration"})
    assert not midia.serve({**foto, "titulo": None, "url": "https://x/b.png"})
    assert midia.serve({**foto, "titulo": "roadmap meeting"})  # 'map' só como palavra inteira


def test_candidatos_intercalam_os_bancos(monkeypatch):
    """A visão só vê os primeiros: em busca genérica a Commons trazia só foto antiga e escondia o Openverse."""
    mk = lambda f, n: [{"tipo": "foto", "titulo": f"{f}{i}", "url": f"https://{f}/{i}.jpg"} for i in range(n)]
    monkeypatch.setattr(midia, "commons", lambda q, t, n: mk("commons", 4) if t == "foto" else [])
    monkeypatch.setattr(midia, "openverse", lambda q, n: mk("ov", 4))
    monkeypatch.setattr(midia, "pixabay", lambda q, t, n: [])
    cs = midia.candidatos(["x"], "foto")
    assert [c["titulo"] for c in cs[:4]] == ["commons0", "ov0", "commons1", "ov1"]


def test_banco_fora_do_ar_nao_derruba_os_outros(monkeypatch):
    def cai(*a):
        raise RuntimeError("504 Gateway Timeout")
    monkeypatch.setattr(midia, "openverse", cai)
    monkeypatch.setattr(midia, "pixabay", lambda q, t, n: [])
    monkeypatch.setattr(midia, "commons", lambda q, t, n: [{"tipo": "foto", "titulo": "ok", "url": "https://c/1.jpg"}] if t == "foto" else [])
    assert [c["titulo"] for c in midia.candidatos(["x"], "foto")] == ["ok"]


def test_sem_modelo_de_visao_a_cena_fica_sem_midia(monkeypatch, cfg):
    """Escolher sem ver a imagem não garante relevância: por padrão, nada de mídia."""
    from videobot import llm
    monkeypatch.setattr(midia, "miniatura", lambda url, lado=400: None)
    chamou = []
    monkeypatch.setattr(llm, "gerar_json", lambda *a, **k: chamou.append(1) or ({"escolha": 0}, {}, "x"))
    sc = {"id": "s", "text": "robôs na fábrica"}
    assert midia.escolher(sc, [{"tipo": "foto", "titulo": "t", "url": "u", "thumb": "t"}], cfg) == -1
    assert not chamou


def test_video_vira_quadros_no_tamanho_da_tela(tmp_path):
    src = tmp_path / "v.mp4"
    ffmpeg("-f", "lavfi", "-i", "testsrc=size=640x360:rate=30:duration=3", "-pix_fmt", "yuv420p", src)
    n = midia.quadros_video(src, tmp_path / "q", 2.0, 108, 192, 30)
    assert 55 <= n <= 62
    from PIL import Image
    assert Image.open(tmp_path / "q" / "q0001.jpg").size == (108, 192)


def test_video_curto_repete_ate_cobrir_a_cena(tmp_path):
    src = tmp_path / "v.mp4"
    ffmpeg("-f", "lavfi", "-i", "testsrc=size=320x240:rate=30:duration=1", "-pix_fmt", "yuv420p", src)
    assert midia.quadros_video(src, tmp_path / "q", 3.0, 64, 112, 30) >= 85


def test_credito_diz_foto_ou_video_autor_e_licenca():
    c = {"tipo": "video", "autor": "Fulano", "fonte": "Openverse/flickr", "licenca": "CC BY 2.0"}
    assert midia.credito(c) == "Vídeo: Fulano / Openverse (CC BY 2.0)"


# ---------------------------------------------------------------- relevância dos objetos 3D
def test_objeto_so_entra_se_ligado_a_fala_da_cena():
    """Run #19: foguete em '36 milhões de empregos perdidos' e chip em '30% dos trabalhos' (ligados só ao tema)."""
    sc = {"text": "A automação pode cortar vinte e um por cento dos empregos.", "objetos3d": ["foguete", "chip"], "params": {}}
    objs = objetos3d.escolher(sc, "SpaceX e chips")
    assert "foguete" not in objs and "chip" not in objs
    assert "pessoas" in objs


def test_milhoes_sem_dinheiro_nao_vira_moedas():
    sc = {"text": "Seis milhões de trabalhadores estão expostos.", "params": {}}
    assert "moedas" not in objetos3d.escolher(sc, "")


def test_cena_sem_nada_concreto_fica_sem_objeto():
    assert objetos3d.escolher({"text": "E você, concorda? Comente sim ou não.", "params": {}}, "IA") == []


def test_revisao_da_ia_manda_e_cena_com_midia_fica_sem_3d(monkeypatch, cfg):
    from videobot import llm
    rot = {"tema": "x", "chapters": [{"scenes": [
        {"id": "a", "text": "fala a", "params": {}},
        {"id": "b", "text": "fala b", "params": {"_photo": "file:///f.jpg"}}]}]}
    monkeypatch.setattr(llm, "gerar_json", lambda *a, **k: ({"cenas": [{"id": "a", "objetos": ["datacenter", "inexistente"]}]}, {}, "x"))
    assert objetos3d.revisar(rot, cfg) == 1
    objetos3d.para_cenas(rot)
    a, b = rot["chapters"][0]["scenes"]
    assert a["params"]["_3d"]["objetos"] == ["datacenter"]
    assert b["params"]["_3d"]["objetos"] == []


# ---------------------------------------------------------------- motor: vídeo, crédito e 3D desligado
@pytest.mark.lento
def test_motor_mostra_video_quadro_a_quadro_e_desliga_3d(tmp_path, cfg):
    import io
    from PIL import Image, ImageChops, ImageStat
    from videobot import render, util
    util.garantir_gsap()
    ffmpeg("-f", "lavfi", "-i", "testsrc=size=1080x1920:rate=30:duration=2", "-q:v", "3", tmp_path / "q%04d.jpg")
    seg = lambda i, p: {"id": f"s{i}", "kind": "scene", "template": "headline", "start": i * 2.0, "dur": 2.0, "text": "x",
                        "params": {"text": "x", "_3d": {"objetos": ["lupa"], "camera": "orbita"}, **p}}
    video = {"_video": {"dir": tmp_path.resolve().as_uri() + "/", "n": 60, "fps": 30}, "_credit": "Vídeo: Fulano / Pixabay (Licença Pixabay)"}
    data = {"w": 1080, "h": 1920, "fps": 30, "duration": 4, "captions": [], "showCaptions": False, "brand": "", "brandLogo": "",
            "brandLogoOpacity": 0, "brandLogoPeriod": 9, "scene3d": "tema", "scale3d": 0.5, "theme": render._tema(cfg["visual"]),
            "segments": [seg(0, video), seg(1, {})]}
    pw, br, pg = render._abrir(1080, 1920)
    erros = []
    pg.on("pageerror", lambda e: erros.append(str(e)))
    try:
        render._boot(pg, data)
        cdp = pg.context.new_cdp_session(pg)
        shot = lambda t: (pg.evaluate("t => window.renderAt(t)", t), Image.open(io.BytesIO(render._shot(cdp, "png"))).convert("RGB"))[1]
        a, b = shot(0.3), shot(1.6)
        assert ImageStat.Stat(ImageChops.difference(a, b)).mean[0] > 3, "o vídeo não andou"
        assert pg.evaluate("() => document.getElementById('gl3d').style.visibility") == "hidden"
        assert pg.evaluate("() => document.getElementById('credit').textContent").startswith("Vídeo: Fulano")
        shot(2.5)
        assert pg.evaluate("() => document.getElementById('gl3d').style.visibility") == "visible"
    finally:
        br.close(); pw.stop()
    assert not erros, erros
