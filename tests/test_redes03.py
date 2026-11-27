"""Episódio #03 (splitter) com cena própria e a regra do render às 00h para episódio pesado e aprovado (27/11)."""
from __future__ import annotations

import copy
import datetime as dt
import json
import re
from pathlib import Path

import yaml

from videobot import pauta

RAIZ = Path(__file__).resolve().parents[1]
CFG = yaml.safe_load((RAIZ / "config.yml").read_text(encoding="utf-8"))
ROT = json.loads((RAIZ / "roteiros" / "redes_ep03.json").read_text(encoding="utf-8"))
JS = (RAIZ / "engine" / "videos" / "redes03.js").read_text(encoding="utf-8")
ENG = (RAIZ / "engine" / "engine.js").read_text(encoding="utf-8")
CENAS = [sc for ch in ROT["chapters"] for sc in ch["scenes"]]


def _raiz(tmp_path, rot, hist):
    (tmp_path / "historico").mkdir(parents=True); (tmp_path / "roteiros").mkdir(parents=True)
    (tmp_path / "historico" / "temas.json").write_text(json.dumps(hist), encoding="utf-8")
    (tmp_path / "roteiros" / "redes_ep03.json").write_text(json.dumps(rot), encoding="utf-8")
    return tmp_path


def test_render_as_00h_so_com_episodio_pesado_e_aprovado(tmp_path):
    hist = [{"data": "2026-11-24", "serie": "redes", "episodio": 1}, {"data": "2026-11-26", "serie": "redes", "episodio": 2}]
    dia = dt.date(2026, 11, 28)
    assert not pauta.render_cedo(CFG, dia, _raiz(tmp_path / "a", {"render_cedo": True, "aprovado": False}, hist)), "sem aprovação não roda"
    assert pauta.render_cedo(CFG, dia, _raiz(tmp_path / "b", {"render_cedo": True, "aprovado": True}, hist))
    assert not pauta.render_cedo(CFG, dt.date(2026, 11, 27), _raiz(tmp_path / "c", {"render_cedo": True, "aprovado": True}, hist)), "27/11 não é dia da série"
    assert not pauta.render_cedo(CFG, dia, _raiz(tmp_path / "d", {"render_cedo": False, "aprovado": True}, hist)), "episódio leve fica no horário normal"


def test_workflow_tem_execucao_as_00h_condicionada():
    wf = (RAIZ / ".github" / "workflows" / "video-diario.yml").read_text(encoding="utf-8")
    assert 'cron: "7 3 * * *"' in wf and 'cron: "47 4 * * *"' in wf
    assert 'github.event.schedule }}" = "7 3 * * *"' in wf and "python -m videobot.pauta --cedo" in wf


def test_episodio_03_tem_cena_propria_sem_reaproveitar_o_02():
    assert ROT["cena3d"] == "video:redes03" and "window.VIDEO3D.redes03 = M3" in JS
    js02 = (RAIZ / "engine" / "videos" / "redes02.js").read_text(encoding="utf-8")
    assert "function plcCaixa" in JS and "function plcCaixa" not in js02
    pecas = set(re.findall(r"'([a-z_]+)'", re.search(r"M3\.PECAS = \[([^\]]+)\]", JS).group(1)))
    assert {sc["params"]["peca"] for sc in CENAS} <= pecas
    assert "transmission" not in JS, "sem vidro de transmissão real: o render fica rápido"


def test_diagramas_novos_do_03_existem_no_motor():
    tipos = {sc["params"]["tipo"] for sc in CENAS if sc["template"] == "diagrama"}
    assert tipos == {"potencia_arvore", "formula", "plc_fbt", "balanceado", "cascata"}
    for t in tipos:
        assert f"tipo === '{t}'" in ENG


def test_roteiro_03_tecnicamente_correto_e_cabe_no_shorts():
    txt = " ".join(sc["text"] for sc in CENAS)
    assert not re.search(r"\d", txt)
    assert len(txt.split()) <= 360, "~2,5 min de fala: cabe nos 3 min do Shorts com a cena de seguir"
    assert CENAS[-1]["text"] == "No próximo vídeo, vamos aprender a diferença entre conector APC e UPC."
    eng = ENG
    for v in ("3,5", "7,2", "10,5", "13,8", "17,1", "20,5"):
        assert f"'{v}'" in eng
    assert ROT["thumb"]["serie"]["ep"] == 3 and "#03" in ROT["publicacao"]["youtube"]["titulo"]
    assert ROT["render_cedo"] is True


def test_ate_128_clientes_por_porta_pon():
    """27/11: o canal adota o padrão atual de até 128 clientes por porta PON (1:8 x 1:16, com óptica C+)."""
    sc = {s["id"]: s for s in CENAS}
    assert "128" in sc["gancho"]["params"]["text"] and "cento e vinte e oito" in sc["gancho"]["text"]
    assert [i["value"] for i in sc["clientes"]["params"]["items"]] == [8, 16, 128]
    assert "classe C mais" in sc["clientes"]["text"]
    assert "64 clientes" not in json.dumps(ROT, ensure_ascii=False)
    assert "até 1:128" in CFG["serie"]["referencias"]
