"""Pauta de 22/11 (IPO da Anthropic): tema marcado para o dia, curto E longo, roteiro educativo com voz de apresentador,
carimbos coerentes com a fala, paleta Claude e fundo de terminal."""
from __future__ import annotations

import copy
import datetime as dt
import json
from pathlib import Path

import pytest

from videobot import elementos, pauta, render, script, script_longo
from videobot.pipeline import escolher_paleta, roteiro_do_formato

RAIZ = Path(__file__).resolve().parents[1]
DIA = dt.date(2026, 11, 22)


def _cfg_pauta(cfg):
    c = copy.deepcopy(cfg)
    c["pautas"] = {DIA.isoformat(): {"tema": "O IPO da Anthropic", "formatos": ["curto", "longo"], "financas": True,
                                     "buscas_fatos": ["Anthropic IPO"], "angulo": "explicar o IPO",
                                     "config": {"roteiro": {"estilo": "educativo", "notas": "Explique o que é um IPO."},
                                                "visual": {"paleta": "claude", "fundo": "terminal"},
                                                "narracao": {"direcao": "apresentador sério"}}}}
    return c


# ---------------------------------------------------------------- pauta e formatos do dia
def test_pauta_do_dia_gera_curto_e_longo_mesmo_disparada_pelo_pc(cfg):
    """O PC dispara a rotina sem tema (formato padrão 'curto'): no dia da pauta saem os dois formatos."""
    c = _cfg_pauta(cfg)
    assert pauta.formatos(c, DIA, "schedule") == ["curto", "longo"]
    assert pauta.formatos(c, DIA, "workflow_dispatch", "curto") == ["curto", "longo"]


def test_tema_ou_refazer_pedidos_na_execucao_ignoram_a_pauta(cfg):
    c = _cfg_pauta(cfg)
    assert pauta.formatos(c, DIA, "workflow_dispatch", "longo", tema_in="outro tema") == ["longo"]
    assert pauta.formatos(c, DIA, "workflow_dispatch", "curto", refazer="45") == ["curto"]
    assert pauta.formatos(c, DIA + dt.timedelta(days=1), "schedule") == [c["formato"]]


def test_aplicar_pauta_poe_tema_buscas_e_ajustes_do_dia(cfg):
    c = _cfg_pauta(cfg)
    p = pauta.aplicar(c, DIA)
    assert p and c["tema"]["tema_fixo"] == "O IPO da Anthropic"
    assert c["tema"]["buscas_fatos"] == ["Anthropic IPO"] and c["tema"]["financas"] is True
    assert c["roteiro"]["estilo"] == "educativo" and c["visual"]["fundo"] == "terminal"
    assert c["narracao"]["direcao"] == "apresentador sério"
    assert c["visual"]["paletas"]["laranja"]  # o resto do config continua lá
    assert pauta.aplicar(_cfg_pauta(cfg), DIA + dt.timedelta(days=1)) is None


def test_linha_de_comando_aplica_a_pauta_quando_nao_vem_tema(monkeypatch, cfg):
    from videobot import __main__ as cli
    import videobot.pipeline as pl
    visto = {}
    monkeypatch.setattr(cli, "carregar_config", lambda *a, **k: _cfg_pauta(cfg))
    monkeypatch.setattr(pauta, "hoje_brasilia", lambda: DIA)
    monkeypatch.setattr(pl, "executar", lambda c, modo, refazer: visto.update(c=c))
    cli.main(["run", "--formato", "longo"])
    c = visto["c"]
    assert c["tema"]["tema_fixo"] == "O IPO da Anthropic" and c["formato"] == "longo" and c["roteiro"]["estilo"] == "educativo"
    cli.main(["run", "--tema", "outra coisa"])
    assert visto["c"]["tema"]["tema_fixo"] == "outra coisa" and visto["c"]["roteiro"].get("estilo") != "educativo"


def test_config_tem_a_pauta_do_ipo_da_anthropic_para_22_11():
    import yaml
    c = yaml.safe_load((RAIZ / "config.yml").read_text(encoding="utf-8"))
    p = c["pautas"]["2026-11-22"]
    assert "Anthropic" in p["tema"] and p["formatos"] == ["curto", "longo"] and p["financas"] is True
    assert p["config"]["roteiro"]["estilo"] == "educativo"
    assert p["config"]["visual"] == {"paleta": "claude", "fundo": "terminal"}
    assert "apresentador" in p["config"]["narracao"]["direcao"] and "robótica" in p["config"]["narracao"]["direcao"]
    assert pauta.formatos(c, DIA, "schedule") == ["curto", "longo"]


def test_checagem_de_fatos_usa_as_buscas_e_o_angulo_da_pauta(monkeypatch, cfg):
    from videobot import facts
    c = _cfg_pauta(cfg)
    pauta.aplicar(c, DIA)
    monkeypatch.setattr(facts, "_plano", lambda cand, cfg: ({"tema_pt": "IPO", "angulo": "outro", "financas": False,
                                                            "buscas": ["x1", "x2"]}, "m"))
    feitas = []
    monkeypatch.setattr(facts, "buscar", lambda q, cfg, dias=None: feitas.append(q) or [])
    out = facts.coletar({"tema": "O IPO da Anthropic"}, c)
    assert feitas[0] == "Anthropic IPO" and "x1" in feitas
    assert out["financas"] is True and out["angulo"] == "explicar o IPO"


# ---------------------------------------------------------------- GitHub: um job por formato, histórico sem conflito
def test_workflow_faz_um_job_por_formato_do_dia():
    wf = (RAIZ / ".github" / "workflows" / "video-diario.yml").read_text(encoding="utf-8")
    assert "python -m videobot.pauta --evento" in wf and "fromJson(needs.checar.outputs.formatos)" in wf
    assert "max-parallel: 1" in wf and "fail-fast: false" in wf
    assert "IN_FORMATO: ${{ matrix.formato }}" in wf
    assert "matrix.formato == inputs.formato && inputs.duracao" in wf, "70 (segundos do curto) não pode virar 70 minutos no longo"
    assert "video-${{ github.run_number }}${{ matrix.formato == 'longo' && '-longo' || '' }}" in wf
    assert "python -m videobot.pauta --mesclar" in wf and "git reset -q --hard origin/main" in wf


def test_historico_dos_dois_jobs_e_mesclado_sem_perder_entrada(tmp_path):
    base = [{"data": "2026-11-21", "tema": "Deepfakes"}]
    curto = base + [{"data": "2026-11-22", "tema": "O IPO da Anthropic", "formato": "curto"}]
    longo = base + [{"data": "2026-11-22", "tema": "O IPO da Anthropic", "formato": "longo"}]
    out = pauta.mesclar_temas(curto, longo)
    assert [e.get("formato") for e in out] == [None, "curto", "longo"]
    (tmp_path / "historico").mkdir()
    (tmp_path / "historico" / "temas.json").write_text(json.dumps(curto), encoding="utf-8")
    nosso = tmp_path / "nosso.json"; nosso.write_text(json.dumps(longo), encoding="utf-8")
    pauta.mesclar_arquivos(tmp_path, nosso)
    assert len(json.loads((tmp_path / "historico" / "temas.json").read_text(encoding="utf-8"))) == 3


def test_refazer_dia_com_dois_formatos_pega_o_roteiro_do_formato_pedido(tmp_path):
    a, b = tmp_path / "a" / "roteiro.json", tmp_path / "b" / "roteiro.json"
    for p, f in ((a, "curto"), (b, "longo")):
        p.parent.mkdir(); p.write_text(json.dumps({"formato": f}), encoding="utf-8")
    assert roteiro_do_formato([a, b], "longo") == b
    assert roteiro_do_formato([a, b], "curto") == a


# ---------------------------------------------------------------- roteiro educativo
FATOS = {"tema": "O IPO da Anthropic", "angulo": "", "financas": True,
         "fatos": [{"id": 1, "afirmacao": "A empresa vale 100 bilhões", "numeros": ["100 billion"], "fonte": "x.com", "data": "", "lado": ""}]}


def test_roteiro_educativo_tem_estrutura_e_tom_de_apresentador(cfg):
    c = _cfg_pauta(cfg); pauta.aplicar(c, DIA); c["formato"] = "curto"
    p = script._prompt({"tema": "IPO"}, FATOS, c, DIA, script._alvos(c))
    for parte in ("GANCHO", "INTRODUÇÃO", "DESENVOLVIMENTO", "CONCLUSÃO", "apresentador de jornal financeiro"):
        assert parte in p
    assert "levemente irônico" not in p and "empolgado, com espanto" not in p
    assert "Explique o que é um IPO." in p
    assert "telejornal" in script._prompt_critico({"chapters": []}, c)


def test_roteiro_viral_continua_igual_sem_pauta(cfg):
    c = copy.deepcopy(cfg); c["formato"] = "curto"
    p = script._prompt({"tema": "x"}, FATOS, c, DIA, script._alvos(c))
    assert "levemente irônico" in p and "ORIENTAÇÕES DESTE VÍDEO" not in p


def test_longo_educativo_usa_estrutura_explicativa_nos_dois_pedidos(cfg):
    c = _cfg_pauta(cfg); pauta.aplicar(c, DIA); c["formato"] = "longo"
    alvos = script._alvos(c)
    pe = script_longo.prompt_estrutura({"tema": "IPO"}, FATOS, c, DIA, alvos)
    est = {"promessa": "p", "capitulos": [{"title": "A"}, {"title": "B"}, {"title": "C"}]}
    pc = script_longo.prompt_capitulo({"tema": "IPO"}, FATOS, c, DIA, est, 1, 200, "")
    for p in (pe, pc):
        assert "ESTRUTURA DE VÍDEO EXPLICATIVO" in p and "Explique o que é um IPO." in p
        assert "leve ironia" not in p
    assert "irônico, sorrindo" not in pc


# ---------------------------------------------------------------- carimbos coerentes
@pytest.mark.parametrize("carimbo,fala,fato,esperado", [
    ("MITO", "A empresa fatura cinco bilhões por ano.", True, ""),               # 21/11: MITO em cima de fato
    ("MITO", "Muita gente acha que a IA não dá lucro. É mito.", True, "MITO"),
    ("CONFIRMADO", "A empresa protocolou o pedido.", True, "CONFIRMADO"),
    ("CONFIRMADO", "Imagine o que vem por aí.", False, ""),
    ("ALERTA", "O Papa aparece vestindo um casaco.", True, ""),                  # 21/11: ALERTA em cena neutra
    ("ALERTA", "O risco é a concorrência com o Google.", True, "ALERTA"),
    ("EM QUEDA", "As ações subiram vinte por cento.", True, ""),
    ("EM ALTA", "As ações subiram vinte por cento.", True, "EM ALTA"),
    ("ESTIMATIVA", "A receita deve chegar a dez bilhões.", True, "ESTIMATIVA"),
    ("FALSO", "Isso não é verdade.", True, "MITO"),
    ("ESPIÃ", "qualquer coisa", True, ""),
])
def test_carimbo_so_entra_quando_a_fala_diz_aquilo(carimbo, fala, fato, esperado):
    assert elementos.carimbo_coerente(carimbo, fala, fato) == esperado


def test_quadro_usa_o_carimbo_coerente_e_espacado():
    src = (RAIZ / "videobot" / "elementos.py").read_text(encoding="utf-8")
    assert "carimbo_coerente(carimbo_seguro(" in src and "cenas_desde_carimbo < 2" in src
    assert '"MITO" (SÓ se a fala desmente' in src


# ---------------------------------------------------------------- paleta Claude e fundo terminal
def test_paleta_claude_fica_fora_do_rodizio(cfg):
    c = copy.deepcopy(cfg); c["visual"]["paleta"] = "rodizio"
    hist = [{"paleta": "azul"}]
    assert escolher_paleta(c, hist, DIA) != "claude"
    c2 = copy.deepcopy(cfg); c2["visual"]["paleta"] = "rodizio"
    assert escolher_paleta(c2, [{"paleta": "claude"}, {"paleta": "laranja"}], DIA) == "roxo"


def test_paleta_claude_leva_as_cores_de_base_e_o_terminal_ao_motor(cfg):
    c = copy.deepcopy(cfg); c["visual"]["paleta"] = "claude"; c["visual"]["fundo"] = "terminal"
    assert escolher_paleta(c, [], DIA) == "claude"
    t = render._tema(c["visual"], "O IPO da Anthropic")
    assert t["accent"].lower() == "#d97757" and t["vars"]["--ink-900"] == "#141413" and t["vars"]["--bg-rgb"] == "20,20,19"
    assert t["fundo"] == "terminal" and t["termTitle"] == "O IPO da Anthropic"
    assert "fundo" not in render._tema(cfg["visual"])  # sem pedir, nada muda


def test_motor_tem_fundo_terminal_e_3d_transparente():
    js = (RAIZ / "engine" / "engine.js").read_text(encoding="utf-8")
    assert "function updateTerminal(t)" in js and "Object.entries(ST.theme.vars" in js
    t3 = (RAIZ / "engine" / "tema3d.js").read_text(encoding="utf-8")
    assert "alpha: TERM" in t3 and "S.background = TERM ? null" in t3


@pytest.mark.lento
def test_render_mostra_o_terminal_com_as_cores_da_claude(cfg):
    """Render real: o terminal aparece digitando, as cores de base da paleta valem e o texto muda com o tempo."""
    from videobot import util
    util.garantir_gsap()
    c = copy.deepcopy(cfg); c["visual"]["paleta"] = "claude"; c["visual"]["fundo"] = "terminal"
    escolher_paleta(c, [], DIA)
    segs = [{"id": "s0", "kind": "scene", "template": "headline", "start": 0, "dur": 12, "text": "x", "params": {"text": "Oi"}}]
    data = {"w": 1920, "h": 1080, "fps": 30, "duration": 12, "captions": [], "showCaptions": False, "brand": "",
            "brandLogoPeriod": 9, "scene3d": "", "scale3d": 0.5, "theme": render._tema(c["visual"], "O IPO da Anthropic"), "segments": segs}
    pw, br, pg = render._abrir(1920, 1080)
    try:
        render._boot(pg, data)
        pg.evaluate("t => window.renderAt(t)", 2.0)
        a = pg.evaluate("() => document.querySelector('#term .term-body').textContent")
        pg.evaluate("t => window.renderAt(t)", 10.0)
        b = pg.evaluate("() => document.querySelector('#term .term-body').textContent")
        ink = pg.evaluate("() => getComputedStyle(document.documentElement).getPropertyValue('--ink-900').trim()")
        cls = pg.evaluate("() => document.getElementById('stage').className")
    finally:
        br.close(); pw.stop()
    assert "claude" in a and len(b) > len(a) and "O IPO da Anthropic" in b
    assert ink == "#141413" and "fundo-terminal" in cls


# ---------------------------------------------------------------- pronúncia
def test_voz_fala_anthropic_ipo_e_claude_do_jeito_certo(cfg):
    """A voz lia 'Anthropic' e 'IPO' em português; a legenda continua com a grafia original."""
    from videobot import tts
    pron = cfg["narracao"]["pronuncia"]
    txt = tts.falado("A Anthropic, dona do Claude, prepara o IPO. Os IPOs de anthropic e ipo grandes.", pron)
    assert txt == "A Antrópic, dona do Clód, prepara o aipiou. Os aipious de Antrópic e aipiou grandes."
    assert tts.falado("Tipos de chipotle e IPOD", pron) == "Tipos de chipotle e IPOD"  # só a palavra inteira
    assert tts.falado("GPON e ONU", pron) == "Gêpon e Ó-Ene-U"
