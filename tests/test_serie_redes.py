"""Série "Redes na Prática" (pedido de 23/11): episódios curtos para técnicos de telecom, um dia sim e outro não,
título e capa numerados, paleta fixa, gancho para o próximo episódio e cenas técnicas (terminal, topologia, faixa)."""
from __future__ import annotations

import copy
import datetime as dt
import re
from pathlib import Path

import yaml

from videobot import objetos3d, pauta, script, serie

RAIZ = Path(__file__).resolve().parents[1]
CFG = yaml.safe_load((RAIZ / "config.yml").read_text(encoding="utf-8"))
INICIO = dt.date(2026, 11, 24)


def _cfg(formato="curto"):
    c = copy.deepcopy(CFG)
    c["formato"] = formato
    return c


def _ep(n, data):
    return {"data": data.isoformat(), "serie": "redes", "episodio": n, "tema": "x"}


# ---------------------------------------------------------------- calendário
def test_serie_e_um_dia_sim_outro_nao():
    dias = [serie.dia_da_serie(CFG, INICIO + dt.timedelta(days=i)) for i in range(6)]
    assert dias == [True, False, True, False, True, False]
    assert not serie.dia_da_serie(CFG, INICIO - dt.timedelta(days=2)), "antes do início não tem série"


def test_dia_da_serie_so_o_episodio_e_domingo_tambem_o_longo():
    """Dia de série: um vídeo só (o curto É o episódio). Se cair no domingo, o longo semanal sai também."""
    c = _cfg()
    c["pautas"] = {}
    domingo = dt.date(2026, 11, 29)
    domingo_serie = next(domingo + dt.timedelta(weeks=k) for k in range(4) if serie.dia_da_serie(c, domingo + dt.timedelta(weeks=k)))
    assert pauta.formatos(c, INICIO, "schedule") == ["curto"]
    assert pauta.formatos(c, domingo_serie, "schedule") == ["curto", "longo"]
    longo = _cfg("longo")
    assert serie.aplicar(longo, domingo_serie, []) is None, "o longo de domingo não vira episódio"


def test_numero_do_episodio_vem_do_historico():
    """Episódio que falhou não é pulado; refazer no mesmo dia mantém o número."""
    assert serie.numero_episodio(CFG, [], INICIO) == 1
    h = [_ep(1, INICIO)]
    assert serie.numero_episodio(CFG, h, INICIO + dt.timedelta(days=2)) == 2
    assert serie.numero_episodio(CFG, h, INICIO + dt.timedelta(days=4)) == 2, "dia 26 falhou: o 2 sai no dia 28"
    assert serie.numero_episodio(CFG, h, INICIO) == 1, "refazer no mesmo dia continua sendo o episódio 1"
    outra = [{"data": "2026-11-20", "serie": "outra", "episodio": 7}]
    assert serie.numero_episodio(CFG, outra, INICIO) == 1


# ---------------------------------------------------------------- episódio aplicado
def test_aplicar_poe_tema_cores_estilo_e_gancho():
    c = _cfg()
    info = serie.aplicar(c, INICIO + dt.timedelta(days=2), [_ep(1, INICIO)])
    ep2, ep3 = CFG["serie"]["episodios"][1], CFG["serie"]["episodios"][2]
    assert info["n"] == 2 and info["titulo"] == ep2["titulo"]
    assert c["tema"]["tema_fixo"] == ep2["tema"]
    assert c["tema"]["buscas_fatos"] == ep2["buscas"]
    assert c["visual"]["paleta"] == "redes" and c["visual"]["cena3d"] == "rota", "24/11: cenário contínuo"
    assert c["roteiro"]["estilo"] == "educativo"
    assert c["tema"]["nicho"] == "Redes na Prática · EP 02", "o rótulo de toda cena mostra a série e o episódio"
    assert f"No próximo vídeo, vamos aprender {ep2['proximo']}" in c["roteiro"]["notas"]
    assert ep3["titulo"] == info["proximo_titulo"]
    assert "terminal" in c["roteiro"]["notas"] and "topologia" in c["roteiro"]["notas"]
    assert script._alvos(c)["cenas"] == (12, 16), "episódio tem mais cenas, mais curtas (fluidez)"


def test_fora_do_dia_ou_episodios_esgotados_sai_o_curto_normal():
    assert serie.aplicar(_cfg(), INICIO + dt.timedelta(days=1), []) is None
    todos = [_ep(i + 1, INICIO - dt.timedelta(days=100 - i)) for i in range(len(CFG["serie"]["episodios"]))]
    c = _cfg()
    assert serie.aplicar(c, INICIO, todos) is None
    assert not c["tema"].get("tema_fixo")


def test_paleta_da_serie_fica_fora_do_rodizio_diario():
    from videobot.pipeline import escolher_paleta
    c = _cfg()
    for i in range(10):
        c["visual"]["paleta"] = "rodizio"
        assert escolher_paleta(c, [{"data": "2026-11-01", "paleta": "laranja"}], dt.date(2026, 11, 1) + dt.timedelta(days=i)) != "redes"


# ---------------------------------------------------------------- título, capa e gancho
def _roteiro(com_gancho=False):
    cenas = [{"id": "s1", "text": "A ONU acendeu o LOS.", "template": "headline", "params": {}},
             {"id": "s2", "text": ("No próximo vídeo, vamos aprender a calcular." if com_gancho else "Meça o RX."), "template": "headline", "params": {}},
             {"id": "s9", "text": "Comenta aí!", "template": "cta", "params": {}}]
    return {"formato": "curto", "chapters": [{"title": "x", "scenes": cenas}],
            "publicacao": {"youtube": {"titulo": "Um título qualquer da IA"}, "tiktok": {}}, "thumb": {"lines": [{"text": "X"}], "number": "9"}}


def test_finalizar_numera_titulo_e_capa():
    c = _cfg()
    info = serie.aplicar(c, INICIO, [])
    r = _roteiro(True)
    serie.finalizar(r, info)
    ep1 = CFG["serie"]["episodios"][0]
    assert r["publicacao"]["youtube"]["titulo"] == f"Redes na Prática #01 | {ep1['titulo']}"
    assert r["thumb"]["serie"] == {"nome": "Redes na Prática", "ep": 1, "total": len(CFG["serie"]["episodios"])}
    assert [ln["text"] for ln in r["thumb"]["lines"]] == ep1["capa"] and r["thumb"]["lines"][1]["hl"]
    assert "number" not in r["thumb"], "a capa da série segue um padrão: sem número solto"
    assert r["serie"]["n"] == 1
    assert len(r["chapters"][0]["scenes"]) == 3, "o gancho já estava no roteiro: nada é acrescentado"


def test_gancho_do_proximo_episodio_e_garantido_antes_do_cta():
    info = serie.aplicar(_cfg(), INICIO, [])
    r = _roteiro(False)
    serie.finalizar(r, info)
    cenas = r["chapters"][0]["scenes"]
    assert [s["id"] for s in cenas] == ["s1", "s2", "proximo_ep", "s9"]
    assert cenas[2]["text"].startswith("No próximo vídeo, vamos aprender ")
    assert cenas[2]["params"]["eyebrow"] == "Próximo · EP 02"


def test_titulos_cabem_e_episodios_estao_completos():
    import json
    icones = set(re.findall(r"^\s+([a-z_]+): '", (RAIZ / "engine" / "icons.js").read_text(encoding="utf-8"), re.M))
    eps = CFG["serie"]["episodios"]
    assert len(eps) >= 24
    for i, e in enumerate(eps):
        t = serie.titulo({"nome": CFG["serie"]["nome"], "n": i + 1, "titulo": e["titulo"]})
        assert len(t) <= 61, f"{t}: com ' #shorts' passaria de 70 caracteres"
        assert len(e["capa"]) == 2 and e["icone"] in icones and e["tema"] and e["buscas"]
        if i < len(eps) - 1:
            assert e.get("proximo"), f"episódio {i + 1} sem chamada para o próximo"


def test_pipeline_registra_serie_e_episodio_e_cli_aplica_a_serie():
    pipe = (RAIZ / "videobot" / "pipeline.py").read_text(encoding="utf-8")
    assert 'serie.finalizar(roteiro, cfg["_serie"])' in pipe
    assert '"episodio": roteiro["serie"]["n"]' in pipe
    cli = (RAIZ / "videobot" / "__main__.py").read_text(encoding="utf-8")
    assert "serie.aplicar(cfg, pauta.hoje_brasilia(), historico())" in cli


# ---------------------------------------------------------------- cenas técnicas
def test_cenas_tecnicas_no_catalogo_e_no_motor():
    js = (RAIZ / "engine" / "engine.js").read_text(encoding="utf-8")
    for t in ("terminal", "topologia", "faixa"):
        assert t in script.NOMES and f"- {t}:" in script.TEMPLATES and f"T.{t} = function" in js


def test_cenas_tecnicas_ficam_sem_foto_quadro_e_3d():
    r = {"tema": "Fibra", "chapters": [{"scenes": [
        {"id": "a", "text": "Na OLT, o comando mostra a fibra.", "template": "terminal", "params": {"command": "show ont"}},
        {"id": "b", "text": "A fibra leva a luz.", "template": "headline", "params": {}}]}]}
    objetos3d.para_cenas(r)
    a, b = r["chapters"][0]["scenes"]
    assert a["params"]["_3d"]["objetos"] == []
    assert b["params"]["_3d"]["objetos"][:1] == ["fibra"]
    assert "DENSAS" in (RAIZ / "videobot" / "midia.py").read_text(encoding="utf-8")
    assert "DENSAS" in (RAIZ / "videobot" / "elementos.py").read_text(encoding="utf-8")


def test_objetos_de_rede_nao_aparecem_por_palavra_parecida():
    """'lan' em 'lançamento', 'nat' em 'natural', 'ont' em 'ontem': nada de switch/roteador/ONU por engano."""
    sc = {"text": "Ontem o lançamento natural do canal foi um sucesso.", "params": {}}
    assert not {"switch", "roteador", "onu"} & set(objetos3d.escolher(sc, ""))
    sc = {"text": "A ONU acendeu o LOS e o roteador perdeu o DHCP.", "params": {}}
    assert {"onu", "roteador"} <= set(objetos3d.escolher(sc, ""))


def test_video_avulso_de_wifi_usa_o_visual_de_redes_sem_ser_episodio():
    """23/11: vídeo avulso para usuário residencial no estilo da série (paleta, cenas técnicas), mas fora da série."""
    c = _cfg()
    dia = dt.date(2026, 11, 23)
    p = pauta.aplicar(c, dia)
    assert p and "mesh" in c["tema"]["tema_fixo"].lower()
    assert c["visual"]["paleta"] == "redes" and c["roteiro"]["estilo"] == "educativo"
    # refeito no mesmo dia: o usuário pediu uma ilustração contínua (planta) no lugar de cenas soltas
    assert c["visual"]["cena3d"] == "planta" and c["roteiro"]["so_planta"] is True
    assert script._alvos(c)["cenas"] == (12, 15)
    assert not serie.dia_da_serie(c, dia), "23/11 não é dia de episódio"
    assert serie.aplicar(c, dia, []) is None and "_serie" not in c
    assert pauta.formatos(c, dia, "workflow_dispatch", "") == ["curto"]


# ---------------------------------------------------------------- vídeo de Wi-Fi de 23/11 (FuYCu_Ki6p0)
FATOS = {"fatos": [{"id": 1, "afirmacao": "Um nó mesh cobre de 1.500 pés quadrados; nós a até 30 pés", "numeros": ["1500", "30"], "fonte": "x"}]}


def _valida(sc, minimo=0):
    c = _cfg()
    c["roteiro"]["cenas_tecnicas_min"] = minimo
    return script.validar({"chapters": [{"title": "x", "scenes": [sc]}], "thumb": {"lines": [{"text": "x"}]},
                           "publicacao": {"youtube": {"titulo": "x"}, "tiktok": {"x": 1}}}, FATOS, dict(c, formato="__"), dt.date(2026, 11, 23))


def test_regua_da_faixa_e_rotulos_tecnicos_nao_sao_barrados_pela_checagem():
    """A faixa de -30 a -90 dBm é a régua, não uma afirmação: antes ela era barrada e a cena virava título."""
    faixa = {"id": "f", "text": "Perto do roteador o sinal é forte.", "template": "faixa", "fact_ids": [],
             "params": {"min": -30, "max": -90, "zones": [{"from": -30, "to": -67, "label": "bom", "tone": "good"}], "unit": "dBm"}}
    assert not [e for e in _valida(faixa) if "não está nos fatos" in e]
    faixa["params"]["value"] = -72
    assert [e for e in _valida(faixa) if "-72" in e], "o valor medido continua precisando de fonte"
    topo = {"id": "t", "text": "O sinal vai do roteador ao nó.", "template": "topologia", "fact_ids": [],
            "params": {"nodes": [{"id": "r", "label": "Roteador 5 GHz"}, {"id": "n", "label": "Nó 2"}], "links": [{"from": "r", "to": "n", "label": "9 m"}]}}
    assert not [e for e in _valida(topo) if "não está nos fatos" in e]


def test_unidades_imperiais_sao_recusadas_e_a_conversao_vale_como_fato():
    """'50 pés' e '1 000 ft²' saíram no vídeo; o certo é metro: 9 m (30 pés) e 139 m² (1.500 pés²) batem com o fato."""
    pes = {"id": "p", "text": "Os nós ficam a no máximo trinta pés.", "template": "bignumber", "fact_ids": [1], "params": {"value": 30, "suffix": " ft"}}
    assert any("métricas" in e for e in _valida(pes))
    metro = {"id": "m", "text": "Os nós ficam a no máximo nove metros.", "template": "bignumber", "fact_ids": [1], "params": {"value": 9, "suffix": " m"}}
    area = {"id": "a", "text": "Um nó cobre cento e trinta e nove metros quadrados.", "template": "bignumber", "fact_ids": [1], "params": {"value": 139, "suffix": " m²"}}
    cena = lambda sc: [e for e in _valida(sc) if e.startswith("cena ")]
    assert cena(metro) == [] and cena(area) == []
    libras = {"id": "l", "text": "O vídeo tem tradução em Libras.", "template": "headline", "fact_ids": [], "params": {"text": "Libras"}}
    assert not any("métricas" in e for e in _valida(libras)), "Libras é a língua de sinais, não unidade"


def test_cena_saneada_vira_titulo_da_propria_fala_e_nao_repete():
    c = _cfg()
    cenas = [{"id": f"s{i}", "text": t, "template": "bignumber", "fact_ids": [], "params": {"value": 77 + i}}
             for i, t in enumerate(["Quanto maior a distância, maior a atenuação.", "Paredes de alvenaria absorvem o sinal."])]
    r = {"chapters": [{"title": "Por que o Wi-Fi morre no quarto?", "scenes": cenas}]}
    script._sanear(r, FATOS, c, dt.date(2026, 11, 23))
    textos = [sc["params"]["text"] for sc in cenas]
    assert textos == ["Quanto maior a distância", "Paredes de alvenaria absorvem o sinal"]


def test_video_no_estilo_redes_exige_cenas_tecnicas():
    sc = {"id": "h", "text": "O sinal enfraquece.", "template": "headline", "fact_ids": [], "params": {"text": "x"}}
    assert not any("cena(s) técnica(s)" in e for e in _valida(sc, 0))
    c = _cfg()
    serie.aplicar(c, INICIO, [])
    assert c["roteiro"]["cenas_tecnicas_min"] == 4
    c2 = _cfg()
    pauta.aplicar(c2, dt.date(2026, 11, 23))
    assert c2["roteiro"]["so_planta"], "o vídeo de Wi-Fi é todo técnico: só cenas da planta"
