"""Episódio #02 refeito em 26/11: cena própria (engine/videos/redes02.js), alternância 3D -> diagrama 2D, medidor de
potência, fotos reais rápidas com carimbo e pronúncia das siglas."""
from __future__ import annotations

import json
import re
from pathlib import Path

import yaml

RAIZ = Path(__file__).resolve().parents[1]
ROT = json.loads((RAIZ / "roteiros" / "redes_ep02.json").read_text(encoding="utf-8"))
JS = (RAIZ / "engine" / "videos" / "redes02.js").read_text(encoding="utf-8")
ENG = (RAIZ / "engine" / "engine.js").read_text(encoding="utf-8")
CENAS = [sc for ch in ROT["chapters"] for sc in ch["scenes"]]


def test_motor_carrega_a_cena_propria_do_video():
    assert "startsWith('video:')" in ENG and "'videos/' + ST.scene3d.slice(6) + '.js'" in ENG
    assert "window.VIDEO3D.redes02 = M3" in JS
    assert not re.search(r"GLTFLoader|OBJLoader|\.glb|\.gltf", JS), "só geometria em código"


def test_toda_peca_citada_existe_na_cena():
    pecas = set(re.findall(r"'([a-z_]+)'", re.search(r"M3\.PECAS = \[([^\]]+)\]", JS).group(1)))
    assert {sc["params"]["peca"] for sc in CENAS if sc["params"].get("peca")} <= pecas


def test_cada_equipamento_aparece_em_3d_e_depois_no_diagrama_2d():
    seq = [(sc["template"], sc["params"].get("tipo")) for sc in CENAS]
    for tipo in ("dio", "ceo", "splitter", "cto"):
        i = seq.index(("diagrama", tipo))
        assert CENAS[i - 1]["template"] != "diagrama", f"{tipo}: o diagrama abre depois da peça em 3D"
    for tipo in ("dio", "ceo", "splitter", "cto"):
        assert f"tipo === '{tipo}'" in ENG


def test_medidor_de_potencia_bate_com_a_conta():
    hud = [sc["params"]["hud"] for sc in CENAS if "hud" in sc["params"]]
    assert hud[0] == 5.0 and hud[-1] == -21.1
    assert all(b <= a for a, b in zip(hud, hud[1:])), "a potência só cai ao longo do caminho"
    conta = next(sc for sc in CENAS if sc["id"] == "conta")["params"]["lines"]
    assert any("−26,1 dB" in l for l in conta) and any("−21,1 dBm" in l for l in conta)


def test_fotos_reais_rapidas_com_carimbo_e_creditos():
    fotos = [f for sc in CENAS for f in sc["params"].get("fotos", [])]
    assert len(fotos) >= 10 and all(f.get("rotulo") for f in fotos)
    for f in fotos:
        assert (RAIZ / "engine" / f["src"]).resolve().exists(), f["src"]
    assert "function fotosFlash" in ENG and "fica = f.dur || 1.6" in ENG, "foto fica pouco tempo na tela"
    assert {c["cena"] for c in ROT["creditos_fotos"]} >= {"fusao_foto", "bobina_foto", "medidor_foto", "olt_foto"}


def test_parametros_gpon_corretos():
    txt = json.dumps(ROT, ensure_ascii=False)
    classes = next(sc for sc in CENAS if sc["id"] == "classes")["params"]["bars"]
    assert [b["value"] for b in classes] == [3, 5, 8]
    orc = next(sc for sc in CENAS if sc["id"] == "orcamento")["params"]["bars"]
    assert [b["value"] for b in orc] == [28, 32, 35]
    faixa = next(sc for sc in CENAS if sc["template"] == "faixa")["params"]
    assert faixa["zones"][0]["from"] == -8 and faixa["zones"][0]["to"] == -25 and faixa["value"] == -21.1
    assert not any(re.search(r"\d", sc["text"]) for sc in CENAS), "narração por extenso"
    assert CENAS[-1]["text"] == "No próximo vídeo, vamos aprender como o splitter divide o sinal."
    assert "Redes na Prática #02" in ROT["publicacao"]["youtube"]["titulo"] and ROT["thumb"]["serie"]["ep"] == 2


def test_pronuncia_das_siglas():
    pr = yaml.safe_load((RAIZ / "config.yml").read_text(encoding="utf-8"))["narracao"]["pronuncia"]
    assert pr["DIO"] == "Dê-I-Ó" and pr["CEO"] == "Céu" and pr["CTO"] == "Cê-Tê-Ó"  # 28/11: "Céo" saía "ceó"


def test_miniaturas_do_wikimedia_em_largura_padrao():
    """26/11: miniatura de 480 px e foto de 1600 px davam HTTP 400; nenhuma foto do Commons chegava aos vídeos."""
    m = (RAIZ / "videobot" / "midia.py").read_text(encoding="utf-8")
    assert '"/500px-"' in m and '"iiurlwidth": 1280' in m


def test_workflow_gera_previa_sem_publicar():
    """26/11: o render no PC levou horas; a prévia sai do GitHub com publicar=nao (sem Release, YouTube nem histórico)."""
    wf = yaml.safe_load((RAIZ / ".github" / "workflows" / "video-diario.yml").read_text(encoding="utf-8"))
    ent = (wf.get(True) or wf.get("on"))["workflow_dispatch"]["inputs"]
    assert ent["publicar"]["default"] == "sim" and set(ent["publicar"]["options"]) == {"sim", "nao"}
    passos = {st.get("name"): st.get("if", "") for st in wf["jobs"]["video"]["steps"] if st.get("name")}
    for nome in ("Publicar Release", "Publicar no YouTube", "Salvar histórico de temas"):
        assert "inputs.publicar != 'nao'" in passos[nome], nome
