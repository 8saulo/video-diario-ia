"""24/11: o episódio 1 da série saiu confuso (0 e -10 dBm repetidos, "-30 dBm é ideal" na fibra). Pedido: vídeo do caminho
da internet num cenário contínuo 3D com cenas técnicas 2D por cima, e o mesmo modelo para o resto da série."""
from __future__ import annotations

import copy
import datetime as dt
import json
import re
from pathlib import Path

import yaml

from videobot import pauta, rota, script, serie

RAIZ = Path(__file__).resolve().parents[1]
CFG = yaml.safe_load((RAIZ / "config.yml").read_text(encoding="utf-8"))
JS = (RAIZ / "engine" / "rede3d.js").read_text(encoding="utf-8")
ROT = json.loads((RAIZ / "roteiros" / "2026-11-24_caminho_da_internet.json").read_text(encoding="utf-8"))


def test_locais_do_python_e_do_motor_sao_os_mesmos():
    lista = re.search(r"WRT\.LOCAIS = \[([^\]]+)\]", JS).group(1)
    assert set(re.findall(r"'([a-z_]+)'", lista)) == set(rota.LOCAIS)
    for l in rota.LOCAIS:
        assert f"local('{l}'" in JS


def test_motor_e_pipeline_usam_o_cenario_rota():
    eng = (RAIZ / "engine" / "engine.js").read_text(encoding="utf-8")
    assert "ST.scene3d === 'rota' ? window.WRT" in eng
    assert '<script src="rede3d.js"></script>' in (RAIZ / "engine" / "index.html").read_text(encoding="utf-8")
    pipe = (RAIZ / "videobot" / "pipeline.py").read_text(encoding="utf-8")
    assert 'in ("planta", "rota")' in pipe, "sem fotos, recortes nem objetos 3D por cima do cenário"
    assert not re.search(r"GLTFLoader|OBJLoader|\.glb|\.gltf", JS), "só geometria em código"


def test_roteiro_do_caminho_da_internet():
    cenas = [sc for ch in ROT["chapters"] for sc in ch["scenes"]]
    locs = [sc["params"]["local"] for sc in cenas]
    assert set(locs) <= set(rota.LOCAIS)
    ordem = ["origem", "submarino", "estacao", "operadora", "isp", "concentrador", "cgnat", "switch_borda", "olt", "dio", "ceo", "cto"]
    assert [l for l in locs if l in ordem][:len(ordem)] == ordem, "o caminho segue a ordem pedida"
    assert sum(sc["template"] in ("terminal", "topologia", "faixa", "kpis") for sc in cenas) >= 8, "muitas cenas técnicas"
    assert not any(re.search(r"\d", sc["text"]) for sc in cenas), "narração por extenso"
    faixa = next(sc for sc in cenas if sc["template"] == "faixa")["params"]
    bom = next(z for z in faixa["zones"] if z["tone"] == "good")
    assert (bom["from"], bom["to"]) == (-8, -25) and -25 <= faixa["value"] <= -15, "faixa correta do GPON (não -30 como ideal)"


def test_pauta_de_hoje_aponta_o_roteiro_e_nao_vira_episodio():
    c = copy.deepcopy(CFG); c["formato"] = "curto"
    p = pauta.aplicar(c, dt.date(2026, 11, 24))
    assert p and c["tema"]["roteiro_fixo"].endswith("2026-11-24_caminho_da_internet.json")
    assert c["visual"]["cena3d"] == "rota"


def test_serie_usa_o_cenario_e_os_valores_de_referencia_corretos():
    c = copy.deepcopy(CFG); c["formato"] = "curto"
    serie.aplicar(c, dt.date(2026, 11, 26), [{"data": "2026-11-24", "serie": "redes", "episodio": 1}])
    assert c["visual"]["cena3d"] == "rota" and c["roteiro"]["locais_rota"] is True
    notas = c["roteiro"]["notas"]
    assert "params.local" in notas and "entre -8 e -25 dBm" in notas and "-30 dBm na ONU é" in notas
    assert "péssimo" in CFG["serie"]["referencias"]


def _erros(cenas, **rot):
    c = copy.deepcopy(CFG); c["formato"] = "curto"; c["roteiro"].update(rot)
    r = {"chapters": [{"title": "x", "scenes": cenas}], "thumb": {"lines": [{"text": "x"}]}, "publicacao": {"youtube": {"titulo": "x"}, "tiktok": {"x": 1}}}
    return script.validar(r, {"fatos": []}, c, dt.date(2026, 11, 24))


def _sc(i, local=None, value=None):
    prm = {"text": "x"} if value is None else {"value": value, "label": "x"}
    if local:
        prm["local"] = local
    return {"id": f"s{i}", "text": "Frase.", "template": "headline" if value is None else "bignumber", "fact_ids": [], "params": prm}


def test_validacao_exige_local_em_toda_cena():
    assert any("params.local" in e for e in _erros([_sc(1, "olt"), _sc(2)], locais_rota=True))
    assert any("pelo menos 4 lugares" in e for e in _erros([_sc(1, "olt"), _sc(2, "olt")], locais_rota=True))
    assert not any("params.local" in e or "lugares" in e for e in _erros([_sc(i, l) for i, l in enumerate(["olt", "dio", "ceo", "cto"])], locais_rota=True))


def test_validacao_barra_o_mesmo_numero_em_muitas_cenas():
    """Ep. 1: 0 dBm e -10 dBm em quase todas as cenas."""
    cenas = [_sc(i, value=-10) for i in range(4)]
    assert any("aparecem na tela em mais de 2 cenas" in e for e in _erros(cenas, max_numero_repetido=2))
    assert not any("aparecem na tela" in e for e in _erros(cenas[:2], max_numero_repetido=2))


def test_rotulo_de_zona_estreita_da_faixa_some():
    eng = (RAIZ / "engine" / "engine.js").read_text(encoding="utf-8")
    assert "t.scrollWidth > s.clientWidth - 8) t.style.display = 'none'" in eng
