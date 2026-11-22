"""Feedback do longo do IPO da Anthropic (22/11): voz padrão com emoções no lugar certo, menos pilha de moedas, logos."""
from __future__ import annotations

from pathlib import Path

import yaml

from videobot import elementos, objetos3d, script

RAIZ = Path(__file__).resolve().parent.parent


def _rot(*cenas):
    return {"tema": "t", "chapters": [{"title": "x", "scenes": [dict(c) for c in cenas]}]}


# ---------------------------------------------------------------- voz
def test_voz_padrao_e_a_aprovada_para_todos_os_videos():
    """A direção do capítulo 2 vale para todos: config global, padrão do tts e o mesmo vocabulário nos dois estilos."""
    from videobot import tts
    cfg = yaml.safe_load((RAIZ / "config.yml").read_text(encoding="utf-8"))
    d = cfg["narracao"]["direcao"]
    assert cfg["narracao"]["gemini_voz"] == "Charon"
    assert "contando uma boa história" in d and "sem exagero" in d and "sorriso na voz" not in d
    assert tts.DIRECAO_PADRAO.split(":")[0] == d.split(":")[0]
    assert script.ESTILOS["viral"]["emocoes"] is script.ESTILOS["educativo"]["emocoes"] is script.EMOCOES_PADRAO
    assert all(e in script.EMOCOES_PADRAO for e in script.EMOCOES_LISTA)


def test_emocao_do_cta_e_de_risco_vao_para_o_momento_certo():
    """CTA sempre cordial; fala de perda/risco com tag positiva vira grave; pergunta sem tag vira curiosa."""
    r = _rot({"text": "Quem é a Anthropic?"},
             {"text": "A perda líquida foi enorme.", "emocao": "otimista, caloroso", "template": "bignumber"},
             {"text": "Comente aqui.", "emocao": "reflexivo", "template": "cta"})
    script.emocoes_coerentes(r)
    assert [s["emocao"] for s in r["chapters"][0]["scenes"]] == ["curioso, intrigante", "grave, cauteloso", "cordial e direto"]


def test_emocoes_fora_do_vocabulario_viram_a_mais_proxima_e_nunca_exageram():
    """'empolgado'/'irônico'/'urgente' (estilo antigo) não passam; viram tags sóbrias do vocabulário."""
    r = _rot({"text": "a", "emocao": "empolgado, com espanto"}, {"text": "b", "emocao": "irônico, sorrindo"},
             {"text": "c", "emocao": "urgente, acelerando"})
    script.emocoes_coerentes(r)
    es = [s["emocao"] for s in r["chapters"][0]["scenes"]]
    assert all(e in script.EMOCOES_LISTA for e in es)
    assert not any(w in " ".join(es) for w in ("empolg", "irôn", "urgent"))


def test_nunca_tres_cenas_seguidas_com_a_mesma_emocao_e_enfase_so_com_numero():
    r = _rot(*[{"text": f"cena {i}", "emocao": "firme, analítico"} for i in range(4)],
             {"text": "o mercado reagiu", "emocao": "enfático no número", "template": "headline"})
    script.emocoes_coerentes(r)
    es = [s["emocao"] for s in r["chapters"][0]["scenes"]]
    assert not any(es[i] == es[i + 1] == es[i + 2] for i in range(len(es) - 2))
    assert es[-1] != "enfático no número", "ênfase em número numa cena sem número na tela"


# ---------------------------------------------------------------- moedas
def test_pilha_de_moedas_nao_domina_o_video():
    """Run #49: 4 das 11 cenas com 3D eram a mesma pilha de moedas. Agora: no máximo 2, o resto vira parente."""
    cenas = [{"id": f"c{i}", "text": "a empresa levantou bilhões de dólares em dinheiro", "objetos_revisados": ["moedas"], "params": {}}
             for i in range(5)]
    r = _rot(*cenas)
    objetos3d.para_cenas(r)
    principais = [s["params"]["_3d"]["objetos"][0] for s in r["chapters"][0]["scenes"] if s["params"]["_3d"]["objetos"]]
    assert principais.count("moedas") <= objetos3d.LIMITE_PRINCIPAL
    assert {"cedulas", "cofre"} & set(principais), "o parente (cédulas/cofre) entra no lugar"
    assert all(principais.count(o) <= objetos3d.LIMITE_PRINCIPAL for o in principais)


def test_diversificar_prefere_outro_objeto_da_propria_cena():
    assert objetos3d.diversificar(["moedas", "grafico_alta"], {"moedas": 2}) == ["grafico_alta", "moedas"]
    assert objetos3d.diversificar(["moedas"], {"moedas": 1}) == ["moedas"]
    assert objetos3d.diversificar(["lua"], {"lua": 2}) == [], "sem parente livre: cena sem 3D em vez de repetir"


def test_motor_tem_variacoes_de_moedas_e_os_objetos_novos():
    """Cada id do catálogo tem desenho no motor; moedas sorteia entre 3 variações pela semente da cena."""
    js = (RAIZ / "engine" / "tema3d.js").read_text(encoding="utf-8")
    for k in objetos3d.CATALOGO:
        assert f"KIT.{k} =" in js, f"objeto {k} sem desenho no tema3d.js"
    assert "[moedasPilhas, moedaGigante, moedasTorres]" in js
    assert "cedulas" in objetos3d.CATALOGO and "cofre" in objetos3d.CATALOGO


# ---------------------------------------------------------------- logos
def test_sem_direcao_de_arte_os_logos_citados_saem_mesmo_assim(monkeypatch, tmp_path, cfg):
    """Run #49: a direção de arte caiu por cota e o vídeo saiu sem logo da Anthropic/Claude, nem em 3D."""
    monkeypatch.setattr(elementos, "dirigir", lambda *a, **k: None)
    svg = tmp_path / "l.svg"; svg.write_text('<svg viewBox="0 0 24 24"><path d="M0 0h24v24H0z"/></svg>', encoding="utf-8")
    monkeypatch.setattr(elementos, "logo", lambda n, p: None if n == "__carregar_lista__" else
                        {"svg": svg.resolve().as_uri(), "cor": "#191919" if n == "Anthropic" else "#D97757", "nome": n})
    monkeypatch.setattr(elementos, "_icones", [{"title": "Anthropic", "hex": "191919"}, {"title": "Claude", "hex": "D97757"}])
    rot = _rot({"id": "a", "text": "O IPO da Anthropic abriu o pregão em alta.", "params": {}},
               {"id": "b", "text": "Hoje o modelo Claude atende empresas no mundo todo.", "params": {}})
    elementos.montar(rot, cfg, tmp_path)
    a, b = rot["chapters"][0]["scenes"]
    def marcas(sc):
        q = (sc["params"].get("_quadro") or {}).get("itens") or []
        return {i.get("nome") for i in q if i.get("tipo") == "logo"} | {"3d" for _ in sc.get("objetos_extra") or [] if _.get("svg")}
    assert marcas(a) and marcas(b), "as duas cenas citam a marca e precisam mostrar o logo (quadro ou 3D)"


def test_logo_3d_prefere_a_marca_dita_pelo_nome():
    """'Claude' dito na cena -> logo da Claude, não o da Anthropic pelo apelido."""
    sc = {"id": "x", "text": "O Claude ganhou uma versão nova.", "params": {}}
    elementos.preparar_3d([sc], {"Anthropic": {"texto": "<svg>A</svg>", "cor": "#191919"}, "Claude": {"texto": "<svg>C</svg>", "cor": "#D97757"}})
    assert sc["objetos_extra"][0]["svg"] == "<svg>C</svg>"


def test_logo_escuro_fica_claro_no_3d():
    """Logo da Anthropic é #191919: no fundo escuro do vídeo ele sumiria; o motor clareia cores muito escuras."""
    js = (RAIZ / "engine" / "tema3d.js").read_text(encoding="utf-8")
    i = js.index("KIT.svg3d")
    assert "cor.set(0xf0eee6)" in js[i:i + 3000]
