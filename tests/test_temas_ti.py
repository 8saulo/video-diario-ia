"""Feedback de 23/11: o canal é de TI, não só de IA. Categoria sorteada por dia, energia/data center
saturados ficam vetados por mais tempo e a rotina faz um vídeo longo por semana."""
from __future__ import annotations

import collections
import copy
import datetime as dt
import random
from pathlib import Path

import yaml

from videobot import pauta, research

RAIZ = Path(__file__).resolve().parents[1]
CFG = yaml.safe_load((RAIZ / "config.yml").read_text(encoding="utf-8"))
HOJE = dt.date(2026, 11, 23)
HIST_REAL = [  # os últimos dias do canal: quase tudo IA e energia
    {"data": "2026-11-18", "tema": "Consumo energético da IA"},
    {"data": "2026-11-20", "tema": "Consumo energético da IA"},
    {"data": "2026-11-21", "tema": "Deepfakes: como reconhecer um vídeo falso"},
    {"data": "2026-11-22", "tema": "IPO da Anthropic"},
    {"data": "2026-11-23", "tema": "Por que tanto dinheiro está indo para data centers de IA"},
]


def _cfg():
    return copy.deepcopy(CFG)


def test_config_tem_categorias_de_ti_alem_de_ia():
    """Redes, robôs, carros autônomos, foguetes e notícias de tecnologia entram no sorteio; IA não domina os pesos."""
    cats = CFG["tema"]["categorias"]
    for k in ("redes", "robos", "carros", "espaco", "novidades", "ia"):
        assert k in cats, k
        assert len(cats[k]["temas_reserva"]) >= 3 and cats[k]["buscas"]
    total = sum(float(c["peso"]) for c in cats.values())
    assert float(cats["ia"]["peso"]) / total < 0.15
    for nome, c in cats.items():
        assert len(set(list(c["buscas"]) + list(CFG["tema"]["buscas"]))) >= 12, f"{nome}: o prompt mestre pede ≥ 12 buscas"


def test_buscas_gerais_nao_sao_mais_so_de_ia():
    """Antes as 14 buscas eram de IA ('AI data center', 'AI bubble'...): o YouTube só devolvia IA."""
    assert not any("ai " in f" {b.lower()} " for b in CFG["tema"]["buscas"])


def test_categoria_de_classifica_os_temas_do_historico():
    cats = CFG["tema"]["categorias"]
    assert research.categoria_de("IPO da Anthropic", cats) == "ia"
    assert research.categoria_de("Cabos submarinos: a internet passa pelo fundo do mar", cats) == "redes"
    assert research.categoria_de("Robotáxis: quantas corridas já rodam sem motorista", cats) == "carros"
    assert research.categoria_de("Starship: o maior foguete já construído", cats) == "espaco"
    assert research.categoria_de("Chips de IA: por que a Nvidia vale tanto", cats) == "hardware"


def test_sorteio_nao_repete_a_categoria_dos_ultimos_dias():
    """Com IA nos últimos dias, a categoria do dia nunca é IA."""
    for i in range(40):
        assert research.escolher_categoria(_cfg(), HIST_REAL, HOJE, random.Random(i)) != "ia"


def test_sorteio_varia_entre_muitas_categorias():
    """Em 300 dias sorteados, saem pelo menos 8 categorias e IA fica longe de ser maioria."""
    cont = collections.Counter(research.escolher_categoria(_cfg(), [], HOJE + dt.timedelta(days=i)) for i in range(300))
    assert len(cont) >= 8
    assert cont["ia"] < 300 * 0.15
    assert cont["redes"] > cont["ia"]


def test_sorteio_e_estavel_no_mesmo_dia_e_formato():
    """Re-execução no mesmo dia cai na mesma categoria (o pipeline pode rodar de novo após uma falha)."""
    a = research.escolher_categoria(_cfg(), HIST_REAL, HOJE)
    assert all(research.escolher_categoria(_cfg(), HIST_REAL, HOJE) == a for _ in range(5))


def test_aplicar_categoria_troca_buscas_nicho_e_reserva():
    cfg = _cfg()
    research.aplicar_categoria(cfg, "robos", random.Random(1))
    t = cfg["tema"]
    assert t["nicho"] == "Robôs" and t["categoria"] == "robos"
    assert t["buscas"][0] in CFG["tema"]["categorias"]["robos"]["buscas"]
    assert set(t["temas_reserva"][:len(CFG["tema"]["categorias"]["robos"]["temas_reserva"])]) == \
        set(CFG["tema"]["categorias"]["robos"]["temas_reserva"]), "a reserva começa pelos temas da categoria"
    research.aplicar_categoria(cfg, "espaco", random.Random(1))  # aplicar de novo não acumula a categoria anterior
    assert not set(t["buscas"]) & set(CFG["tema"]["categorias"]["robos"]["buscas"])


def test_energia_e_data_center_ficam_vetados_por_30_dias():
    """O vídeo de 23/11 ('dinheiro em data centers') passou porque o veto de 7 dias só olhava palavras parecidas."""
    t = CFG["tema"]
    hist = [{"data": "2026-11-05", "tema": "Data centers e o custo de energia"}]
    assert research._cansado("Por que tanto dinheiro está indo para data centers de IA", t, hist, HOJE)
    assert research._cansado("Consumo energético da IA", t, hist, HOJE)
    assert not research._cansado("Cabos submarinos: a internet passa pelo fundo do mar", t, hist, HOJE)
    assert not research._cansado("Consumo energético da IA", t, [{"data": "2026-10-01", "tema": "Energia da IA"}], HOJE)


def test_pesquisa_usa_buscas_da_categoria_e_reserva_sem_energia(monkeypatch):
    """Sem referência no YouTube, a reserva vem da categoria sorteada e nunca traz energia/data center."""
    usadas = []
    monkeypatch.setattr(research, "chave", lambda n: "k" if n == "YOUTUBE_API_KEY" else "")
    monkeypatch.setattr(research, "via_api", lambda b, j, p, key: usadas.extend(b) or [])
    monkeypatch.setattr(research, "via_paginas", lambda *a: [])
    cfg = _cfg()
    out = research.pesquisar(cfg, HIST_REAL, HOJE)
    cat = cfg["tema"]["categoria"]
    assert cat and cat != "ia"
    assert set(CFG["tema"]["categorias"][cat]["buscas"]) <= set(usadas)
    temas = [r["tema"] for r in out["ranking"]]
    assert temas[0] in CFG["tema"]["categorias"][cat]["temas_reserva"]
    assert not any(research._cansado(x, cfg["tema"], HIST_REAL, HOJE) for x in temas)


def test_triagem_descarta_referencia_de_assunto_saturado(monkeypatch):
    """Um vídeo viral sobre data centers não vence mais: cai como 'assunto saturado'."""
    monkeypatch.setattr(research, "chave", lambda n: "k" if n == "YOUTUBE_API_KEY" else "")
    hoje = dt.date.today()
    vid = {"id": "v1", "titulo": "Why is so much money pouring into AI data centers?", "canal": "c", "views": 10 ** 6,
           "duracao_s": 50, "descricao": "", "publicado": hoje.isoformat(), "inscritos": 1000, "curtidas": 10, "comentarios": 1,
           "url": "u"}
    monkeypatch.setattr(research, "via_api", lambda *a: [dict(vid)])
    monkeypatch.setattr(research, "gerar_json", lambda *a, **k: ([{"id": "v1", "titulo_ingles": True,
                                                                     "tema_pt": "Dinheiro em data centers de IA"}], {}, "falso"))
    hist = [{"data": (hoje - dt.timedelta(days=10)).isoformat(), "tema": "Consumo energético da IA"}]
    out = research.pesquisar(_cfg(), hist, hoje)
    assert all(r.get("reserva") for r in out["ranking"]), "a referência saturada não entra no ranking"
    assert "assunto saturado" in out["md"] or out["ranking"][0].get("reserva")


def test_longo_uma_vez_por_semana_no_domingo():
    """Sem pauta, a rotina faz curto todo dia e, aos domingos, também o longo (agendada ou disparada pelo PC)."""
    domingo, segunda = dt.date(2026, 11, 29), dt.date(2026, 11, 30)
    cfg = _cfg()
    cfg["pautas"] = {}
    assert pauta.formatos(cfg, domingo, "schedule") == ["curto", "longo"]
    assert pauta.formatos(cfg, domingo, "workflow_dispatch", "") == ["curto", "longo"]
    assert pauta.formatos(cfg, segunda, "schedule") == ["curto"]
    assert pauta.formatos(cfg, domingo, "workflow_dispatch", "curto") == ["curto"], "formato escolhido no disparo manda"
    cfg["longo_semanal"] = ""
    assert pauta.formatos(cfg, domingo, "schedule") == ["curto"]


def test_historico_grava_a_categoria():
    src = (RAIZ / "videobot" / "pipeline.py").read_text(encoding="utf-8")
    assert '"categoria": cfg["tema"].get("categoria", "")' in src
