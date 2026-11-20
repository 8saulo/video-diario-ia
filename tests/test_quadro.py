"""Regressões do quadro de dossiê e da narrativa (19/11/2026)."""
from __future__ import annotations

import datetime as dt

import pytest
from pathlib import Path

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
        {"id": "a", "text": "Jensen Huang, da NVIDIA, foi investigado", "params": {"_photo": "file:///f.jpg", "_credit": "Foto: Y"}},
        {"id": "b", "text": "y", "params": {}}]}]}
    cred = elementos.montar(rot, cfg, tmp_path)
    a, b = rot["chapters"][0]["scenes"]
    q = a["params"]["_quadro"]
    tipos = [i["tipo"] for i in q["itens"]]
    assert tipos[:3] == ["pessoa", "logo", "foto"] and len(tipos) == 4, "no máximo 4 recortes por cena"
    assert "_photo" not in a["params"], "a foto vira recorte e deixa de ocupar a tela inteira"
    assert q["carimbo"] == "" and q["itens"][0].get("destaque"), "carimbo acusatório ('suposta espiã') é barrado"
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


# ---------------------------------------------------------------- relevância (20/11/2026: OpenAI e NVIDIA em todo vídeo)
def test_marca_so_entra_se_citada_na_cena():
    """Runs 39/40: logo da OpenAI em 'IA pode consumir 20%...' e da NVIDIA em 'Servidores respondem por 60%...'."""
    assert not elementos.citado("OpenAI", "IA pode consumir vinte por cento da energia mundial?")
    assert not elementos.citado("NVIDIA", "Servidores respondem por sessenta por cento do consumo")
    assert elementos.citado("NVIDIA", "Só que a Nvidia caiu dezessete por cento")
    assert elementos.citado("OpenAI", "Treinar o GPT-quatro gastou", elementos.APELIDOS_EXTRA["openai"])


def test_pessoa_so_entra_se_citada():
    """Run 40: foto do Bob Iger numa cena que só falava da Disney."""
    assert not elementos.pessoa_citada("Bob Iger", "Vendeu ativos para a Disney por vinte milhões")
    assert elementos.pessoa_citada("Alex Karp", "Alex Karp diz que só dois tipos de pessoas")
    assert elementos.pessoa_citada("Jensen Huang", "e foi aí que Huang respondeu")


def test_montar_barra_marca_e_pessoa_nao_citadas(monkeypatch, tmp_path, cfg):
    from videobot import llm
    monkeypatch.setattr(llm, "gerar_json", lambda *a, **k: ({"cenas": [
        {"id": "a", "pessoas": [{"nome": "Bob Iger", "wiki": "Bob Iger"}], "marcas": ["OpenAI", "NVIDIA"], "manchete": "Bolha estoura"}]}, {}, "m"))
    monkeypatch.setattr(elementos, "foto_pessoa", lambda *a: {"src": "s", "credito": "c", "pagina": "p", "nome": "n"})
    monkeypatch.setattr(elementos, "logo", lambda n, p: None if n == "__carregar_lista__" else {"svg": "s", "cor": "#000000", "nome": n})
    rot = {"tema": "t", "chapters": [{"scenes": [{"id": "a", "text": "Ela valia um bilhão e agora faliu.", "params": {}}]}]}
    elementos.montar(rot, cfg, tmp_path)
    q = rot["chapters"][0]["scenes"][0]["params"].get("_quadro") or {"itens": []}
    assert not [i for i in q["itens"] if i["tipo"] in ("logo", "pessoa")]


def test_alterna_quadro_e_3d():
    """O vídeo não pode ser só recortes: cenas só com peças 2D e com objeto 3D ligado à fala alternam para o 3D."""
    q2d = lambda: {"itens": [{"tipo": "manchete", "texto": "x"}], "reais": 0}
    qreal = lambda: {"itens": [{"tipo": "logo", "nome": "X"}], "reais": 1}
    cenas = [{"params": {"_quadro": qreal()}}, {"params": {"_quadro": qreal()}}, {"params": {"_quadro": q2d()}, "objetos_revisados": ["moedas"]},
             {"params": {"_quadro": q2d()}, "objetos_revisados": ["pessoas"]}, {"params": {"_quadro": q2d()}, "objetos_revisados": ["relogio"]},
             {"params": {"_quadro": q2d()}}]
    elementos.alternar(cenas)
    modos = ["quadro" if c["params"].get("_quadro") else "3d" for c in cenas]
    assert modos[:2] == ["quadro", "quadro"] and "3d" in modos[2:5] and "quadro" in modos[2:5]
    assert modos[5] == "quadro", "sem objeto 3D ligado à fala, a cena mantém as peças 2D"


def test_nome_principal_da_marca_basta():
    """'The Walt Disney Company' foi barrada numa cena que dizia 'vendeu ativos para a Disney'."""
    assert elementos.citado("The Walt Disney Company", "Vendeu ativos para a Disney por vinte milhões")
    assert not elementos.citado("The Walt Disney Company", "Walt saiu da sala")


def test_manchete_com_marca_nao_citada_sai(monkeypatch, tmp_path, cfg):
    """20/11: o recorte dizia 'OpenAI vende ativos à Disney' numa cena que não falava da OpenAI."""
    from videobot import llm
    monkeypatch.setattr(llm, "gerar_json", lambda *a, **k: ({"cenas": [{"id": "a", "manchete": "OpenAI vende ativos à Disney"}]}, {}, "m"))
    monkeypatch.setattr(elementos, "logo", lambda n, p: None)
    monkeypatch.setattr(elementos, "_icones", [{"title": "OpenAI", "hex": "000000"}])
    rot = {"tema": "t", "chapters": [{"scenes": [{"id": "a", "text": "Vendeu ativos para a Disney por vinte milhões.", "params": {}}]}]}
    elementos.montar(rot, cfg, tmp_path)
    q = rot["chapters"][0]["scenes"][0]["params"].get("_quadro") or {"itens": []}
    assert not [i for i in q["itens"] if i["tipo"] == "manchete"]


# ---------------------------------------------------------------- melhorias de 20/11/2026
def test_carimbo_nunca_acusa_ninguem():
    """Risco de difamação: 'SUPOSTA ESPIÃ' ao lado da foto de uma pessoa real."""
    for ruim in ("SUPOSTA ESPIÃ", "golpe!", "Fraude", "criminoso", "MENTIRA"):
        assert elementos.carimbo_seguro(ruim) == ""
    assert elementos.carimbo_seguro("recorde") == "RECORDE"


def test_direcao_de_arte_e_uma_chamada_so_para_quadro_midia_e_3d(monkeypatch, tmp_path, cfg):
    """Menos pedidos por vídeo: a direção de arte traz também as buscas de mídia e os objetos 3D."""
    from videobot import llm, midia
    chamadas = []
    monkeypatch.setattr(llm, "gerar_json", lambda p, *a, **k: chamadas.append(p[:40]) or ({"cenas": [
        {"id": "a", "buscas": ["fiber cable"], "tipo": "foto", "objetos3d": ["pessoas", "foguete"], "manchete": "Fibra chega"}]}, {}, "m"))
    monkeypatch.setattr(midia, "candidatos", lambda b, p: [])
    rot = {"tema": "t", "chapters": [{"scenes": [{"id": "a", "text": "Os trabalhadores instalaram fibra.", "params": {}}]}]}
    arte = elementos.dirigir(rot, cfg)
    midia.aplicar(rot, cfg, tmp_path, {}, 800, 600, 30, plano_pronto=arte)
    elementos.objetos_da_arte(rot, arte)
    assert len(chamadas) == 1
    assert rot["chapters"][0]["scenes"][0]["objetos_revisados"] == ["pessoas"], "foguete não tem ligação com a fala"


def test_critico_reescreve_roteiro_curto_dizendo_quanto_acrescentar(monkeypatch, cfg):
    """Runs de 19-20/11: roteiros com 123 e 136 palavras (meta 144-184) passavam assim mesmo."""
    pedidos = []
    curto = {"chapters": [{"title": "x", "scenes": [{"id": f"c{i}", "text": " ".join(["palavra"] * 14), "template": "headline", "params": {}} for i in range(8)]}],
             "thumb": {"lines": [{"text": "x"}]}, "publicacao": {"youtube": {"titulo": "t"}, "tiktok": {"x": 1}}}
    longo = {**curto, "chapters": [{"title": "x", "scenes": curto["chapters"][0]["scenes"] + [
        {"id": "n1", "text": " ".join(["mais"] * 20), "template": "headline", "params": {}},
        {"id": "n2", "text": " ".join(["mais"] * 20), "template": "headline", "params": {}}]}]}

    def falso(p, *a, **k):
        pedidos.append(p)
        if "editor-chefe" in p:
            return {"gancho": 8, "narrativa": 8, "fluidez": 8, "problemas": []}, {}, "m"
        return longo, {}, "m"
    monkeypatch.setattr(script, "gerar_json", falso)
    erros = script.validar(curto, {"fatos": []}, cfg, dt.date(2026, 11, 20))
    r, _ = script.revisar_narrativa(curto, erros, {"titulo": ""}, {"tema": "t", "fatos": []}, cfg, dt.date(2026, 11, 20), script._alvos(cfg))
    assert any("ACRESCENTE" in p for p in pedidos)
    assert sum(len(sc["text"].split()) for sc in r["chapters"][0]["scenes"]) > 112


def test_reserva_de_pessoa_exige_nome_completo_no_arquivo(monkeypatch, tmp_path):
    """Sem reconhecimento facial: só vale arquivo da Commons com o nome completo da pessoa no título."""
    from videobot import midia
    monkeypatch.setattr(elementos, "_commons_busca", lambda q, f, n=12: [
        {"titulo": "Karp at a conference.jpg", "thumb": "u1", "lic": "cc-by-2.0", "licenca": "CC BY 2.0", "autor": "a", "w": 900, "h": 900, "pagina": "p", "mime": "image/jpeg", "url": "u1"},
        {"titulo": "Alex Karp 2023.jpg", "thumb": "u2", "lic": "cc-by-2.0", "licenca": "CC BY 2.0", "autor": "b", "w": 900, "h": 900, "pagina": "p2", "mime": "image/jpeg", "url": "u2"}])
    monkeypatch.setattr(midia, "_baixar", lambda url, dst, limite_mb=80: (dst.write_bytes(url.encode()), dst)[1])
    r = elementos.pessoa_commons("Alex Karp", tmp_path)
    assert r and (tmp_path / "pessoa_alex_karp.jpg").read_bytes() == b"u2"


def test_reserva_de_logo_exige_marca_e_logo_no_nome(monkeypatch, tmp_path):
    from videobot import midia
    monkeypatch.setattr(elementos, "_commons_busca", lambda q, f, n=12: [
        {"titulo": "Disney castle photo.jpg", "thumb": "x", "mime": "image/jpeg"},
        {"titulo": "Disney wordmark logo.svg", "thumb": "y.png", "mime": "image/svg+xml"}])
    monkeypatch.setattr(midia, "_baixar", lambda url, dst, limite_mb=80: (dst.write_bytes(url.encode()), dst)[1])
    r = elementos.logo_commons("Disney", tmp_path)
    assert r and r["fundo"] == "claro" and Path(r["svg"].replace("file:///", "")).name == "logo_disney.png"


def test_cena_sem_quadro_ganha_3d_da_propria_cena(monkeypatch):
    """3D por código ligado ao roteiro: logo citada > número da cena > palavra de destaque."""
    monkeypatch.setattr(elementos, "_icones", [])
    logos = {"NVIDIA": {"texto": "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 2 2'><path d='M0 0h2v2H0z'/></svg>", "cor": "#76B900"}}
    cenas = [{"text": "A Nvidia caiu dezessete por cento", "params": {}},
             {"text": "Valia cinco trilhões", "params": {"value": 5, "prefix": "US$ ", "suffix": " tri", "label": "x", "sub": "y"}},
             {"text": "Ninguém esperava", "params": {"highlight": ["choque"]}}]
    elementos.preparar_3d(cenas, logos)
    assert cenas[0]["objetos_extra"][0]["cor"] == "#76B900"
    assert cenas[1]["objetos_extra"][0]["texto"] and cenas[2]["objetos_extra"][0]["texto"]
    assert elementos._numero_da_cena(cenas[1]["params"]) == "US$ 5 TRI"


def test_cena_so_com_logo_alterna_entre_quadro_e_logo_3d():
    logo = lambda: {"itens": [{"tipo": "logo", "nome": "NVIDIA"}], "reais": 1}
    cenas = [{"params": {"_quadro": logo()}}, {"params": {"_quadro": logo()}}, {"params": {"_quadro": logo()}}]
    elementos.alternar(cenas, {"NVIDIA": {"texto": "<svg/>", "cor": "#76B900"}})
    modos = ["quadro" if c["params"].get("_quadro") else "3d" for c in cenas]
    assert modos == ["quadro", "3d", "quadro"]


def test_no_maximo_dois_quadros_seguidos():
    """Teste de 20/11: 9/9 cenas de quadro (fotos em quase todas) e nenhum 3D."""
    foto = lambda: {"itens": [{"tipo": "foto"}], "reais": 1}
    cenas = [{"params": {"_quadro": foto(), "value": 10 + i, "label": "x"}} for i in range(6)]
    elementos.alternar(cenas, {})
    modos = ["q" if c["params"].get("_quadro") else "3d" for c in cenas]
    assert modos == ["q", "q", "3d", "q", "q", "3d"]


@pytest.mark.lento
def test_texto_do_post_it_e_do_jornal_nao_vaza_do_cartao(tmp_path, cfg):
    """20/11/2026: '35 mil residências' e '550 toneladas' saíam pela borda do post-it (fonte fixa + nowrap)."""
    from videobot import render, util
    util.garantir_gsap()
    q = {"itens": [{"tipo": "manchete", "texto": "Prompt gasta energia de 35 mil casas norte-americanas"},
                   {"tipo": "nota", "valor": "35 mil residências", "rotulo": "equivalente energético anual"},
                   {"tipo": "nota", "valor": "550 toneladas", "rotulo": "CO2"}], "carimbo": "", "etiqueta": ""}
    seg = {"id": "s0", "kind": "scene", "template": "headline", "start": 0, "dur": 3.0, "text": "x", "params": {"text": "x", "_quadro": q}}
    data = {"w": 1080, "h": 1920, "fps": 30, "duration": 3, "captions": [], "showCaptions": False, "brand": "", "brandLogo": "",
            "brandLogoOpacity": 0, "brandLogoPeriod": 9, "scene3d": "tema", "scale3d": 0.5, "theme": render._tema(cfg["visual"]), "segments": [seg]}
    pw, br, pg = render._abrir(1080, 1920)
    try:
        render._boot(pg, data)
        pg.evaluate("t => window.renderAt(t)", 2.5)
        vaza = pg.evaluate("""() => [...document.querySelectorAll('.q-postit, .q-jornal')].flatMap(c => {
            const cw = c.clientWidth, ch = c.clientHeight;
            return [...c.querySelectorAll('.q-postit-valor, .q-postit-rotulo, .q-jornal-texto')].filter(t =>
                t.offsetLeft < -1 || t.offsetLeft + t.scrollWidth > cw + 1 || t.offsetTop + t.scrollHeight > ch + 1 || t.scrollWidth > t.clientWidth + 1
            ).map(t => t.textContent); })""")
    finally:
        br.close(); pw.stop()
    assert not vaza, vaza


@pytest.mark.lento
def test_carimbo_no_jornal_nao_cobre_a_manchete(tmp_path, cfg):
    """20/11/2026: sem foto na cena, o carimbo caía no meio do texto da manchete."""
    from videobot import render, util
    util.garantir_gsap()
    q = {"itens": [{"tipo": "manchete", "texto": "Prompt gasta energia de 35 mil casas"}, {"tipo": "nota", "valor": "35 mil", "rotulo": "casas"}],
         "carimbo": "CONFIRMADO", "etiqueta": ""}
    seg = {"id": "s0", "kind": "scene", "template": "headline", "start": 0, "dur": 3.0, "text": "x", "params": {"text": "x", "_quadro": q}}
    data = {"w": 1080, "h": 1920, "fps": 30, "duration": 3, "captions": [], "showCaptions": False, "brand": "", "brandLogo": "",
            "brandLogoOpacity": 0, "brandLogoPeriod": 9, "scene3d": "tema", "scale3d": 0.5, "theme": render._tema(cfg["visual"]), "segments": [seg]}
    pw, br, pg = render._abrir(1080, 1920)
    try:
        render._boot(pg, data)
        pg.evaluate("t => window.renderAt(t)", 2.8)
        sobre = pg.evaluate("""() => { const c = document.querySelector('.q-carimbo').getBoundingClientRect(),
            t = document.querySelector('.q-jornal-texto').getBoundingClientRect();
            const ix = Math.max(0, Math.min(c.right, t.right) - Math.max(c.left, t.left)), iy = Math.max(0, Math.min(c.bottom, t.bottom) - Math.max(c.top, t.top));
            return ix * iy / (t.width * t.height); }""")
    finally:
        br.close(); pw.stop()
    assert sobre < 0.08, f'carimbo cobre {sobre:.0%} da manchete'
