"""Cenas com tipos trocados pelo modelo não podem derrubar o roteiro (longo de 22/11 caiu com template dict)."""
import datetime

from videobot.script import normalizar_cena
from videobot.script_longo import _erros_capitulo

CFG = {"formato": "longo", "duracao": {"longo_min": 9, "curto_seg": 75}, "tema": {}, "roteiro": {}}
FATOS = {"fatos": [{"id": 1, "afirmacao": "A empresa vale 300 bilhões", "numeros": ["300"], "fonte": "https://exemplo.com", "trecho": "vale 300 bilhões"}]}


def test_template_dict_nao_derruba_validacao_do_capitulo():
    """Reproduz o TypeError 'unhashable type: dict' em validar() com "template": {...}."""
    cenas = [{"id": "a", "text": "palavra " * 40, "template": {"name": "headline", "params": {"text": "Oi"}}, "fact_ids": [1]},
             {"id": "b", "text": "palavra " * 40, "template": ["statement"], "params": "x"}]
    erros = _erros_capitulo(cenas, FATOS, CFG, datetime.date(2026, 11, 22), 80)
    assert not any("template" in e for e in erros)
    assert cenas[0]["template"] == "headline" and cenas[0]["params"] == {"text": "Oi"}
    assert cenas[1]["template"] == "statement" and cenas[1]["params"] == {}


def test_normalizar_cena_conserta_ids_textos_e_fact_ids():
    """id/texto não-string e fact_ids soltos viram os tipos esperados; cena boa fica igual."""
    sc = normalizar_cena({"id": 7, "text": None, "template": "BARS ", "fact_ids": "2"})
    assert sc == {"id": "7", "text": "", "template": "bars", "params": {}, "fact_ids": [2]}
    boa = {"id": "x", "text": "oi", "template": "quote", "params": {"q": 1}, "fact_ids": [1, 3]}
    assert normalizar_cena(dict(boa)) == boa


def test_template_dict_sem_nome_vira_template_invalido_e_e_apontado():
    """Sem nome reconhecível, a validação acusa o template (o modelo corrige no 2º pedido) em vez de quebrar."""
    cenas = [{"id": "a", "text": "palavra " * 80, "template": {"foo": 1}}]
    erros = _erros_capitulo(cenas, FATOS, CFG, datetime.date(2026, 11, 22), 80)
    assert any("template '' não existe" in e for e in erros)


def test_cenas_de_aceita_lista_solta_e_outras_variacoes():
    """A correção do capítulo 7 (22/11) veio como lista de cenas solta e derrubou o longo com AttributeError."""
    from videobot.script_longo import _cenas_de
    a = {"id": "a", "text": "oi"}
    assert _cenas_de([a, {"text": ""}, "lixo"]) == [a]
    assert _cenas_de({"scenes": [a]}) == [a]
    assert _cenas_de({"cenas": [a]}) == [a]
    assert _cenas_de({"chapters": [{"scenes": [a]}]}) == [a]
    assert _cenas_de({"scenes": "x"}) == [] and _cenas_de(None) == [] and _cenas_de("texto") == []


def test_escrever_longo_sobrevive_a_correcao_em_lista_e_estrutura_em_lista(monkeypatch, cfg):
    """Ponta a ponta com o modelo falso: estrutura e correção chegam como listas soltas e o roteiro sai."""
    from videobot import script_longo
    caps = [{"title": f"Cap {i}", "resumo": "x"} for i in range(6)]
    cena = lambda i, n: {"id": f"c{i}_{n}", "text": "palavra " * 12, "template": "headline", "params": {"text": "Oi"}}
    chamadas = {"n": 0}

    def falso(prompt, cfg, **k):
        chamadas["n"] += 1
        if chamadas["n"] == 1:
            return caps, "", "falso"
        if "SEU RASCUNHO TEVE ESTES PROBLEMAS" in prompt:
            return [cena(chamadas["n"], j) for j in range(3)], "", "falso"  # lista solta
        return {"scenes": [cena(chamadas["n"], 0)]}, "", "falso"  # curto demais → pede correção

    monkeypatch.setattr(script_longo, "gerar_json", falso)
    monkeypatch.setattr(script_longo, "_embalar", lambda r, *a, **k: r, raising=False)
    cfg = dict(cfg, formato="longo")
    try:
        script_longo.escrever_longo({"titulo": "t", "tema": "t"}, dict(FATOS, tema="t", angulo="a"), cfg, datetime.date(2026, 11, 22))
    except (AttributeError, TypeError) as e:
        raise AssertionError(f"quebrou com tipo inesperado: {e}")
    except Exception as e:
        print("parou em outra etapa:", repr(e))  # outras etapas (embalagem etc.) podem pedir mais do falso; o que importa é passar pelos capítulos
    assert chamadas["n"] >= 1 + 6 * 2


def test_objeto_e_lista_de_aceitam_respostas_fora_do_formato():
    """Os modelos às vezes trocam objeto por lista (e vice-versa): os helpers devolvem sempre o tipo esperado."""
    from videobot.llm import lista_de, objeto
    assert objeto({"a": 1}) == {"a": 1} and objeto([{"a": 1}]) == {"a": 1}
    assert objeto([{"a": 1}, {"b": 2}]) == {} and objeto("x") == {} and objeto(None) == {}
    assert lista_de({"cenas": [{"id": 1}, "x"]}, "cenas") == [{"id": 1}]
    assert lista_de([{"id": 2}], "cenas") == [{"id": 2}]
    assert lista_de({"cenas": "x"}, "cenas") == [] and lista_de(None, "cenas") == []


def test_validar_aponta_resposta_em_lista_em_vez_de_quebrar(cfg):
    """validar() com lista solta ou capítulos/cenas de tipo errado vira erro para o modelo corrigir, não AttributeError."""
    from videobot.script import validar
    hoje = datetime.date(2026, 11, 22)
    c = dict(cfg, formato="curto")
    assert "objeto JSON" in validar([{"id": "a", "text": "oi"}], FATOS, c, hoje)[0]
    assert validar({"chapters": ["x", {"scenes": ["y"]}]}, FATOS, c, hoje) == ["roteiro sem cenas"]
