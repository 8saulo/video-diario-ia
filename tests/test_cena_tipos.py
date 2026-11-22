"""Cenas com tipos trocados pelo modelo não podem derrubar o roteiro (longo de 22/11 caiu com template dict)."""
import datetime

from videobot.script import normalizar_cena
from videobot.script_longo import _erros_capitulo

CFG = {"formato": "longo", "duracao": {"longo_min": 9, "curto_seg": 75}, "tema": {}, "roteiro": {}}
FATOS = {"fatos": [{"id": 1, "afirmacao": "A empresa vale 300 bilhões", "numeros": ["300"]}]}


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
