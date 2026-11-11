"""Regressões da narração (videobot/tts.py)."""
from __future__ import annotations

from conftest import chiado, concatenar, db_max, fala_sintetica

from videobot import tts


def test_corte_de_cena_nao_emudece_cenas_seguintes(tmp_path, cfg, roteiro_curto, gemini_falso):
    """Bug de 10/11/2026: o afade de saída usava o tempo do trecho inteiro (-ss depois do -i) e
    emudecia toda cena depois da 1ª/2ª; os curtos ficavam com ~7 s de voz."""
    fala = fala_sintetica(tmp_path / "fala.wav", 30)
    gemini_falso["resposta"] = lambda texto, n: fala
    r = tts.narrar(roteiro_curto, cfg, tmp_path / "out")
    assert set(r["cenas"]) == {"c0", "c1", "c2"}
    for cid, c in r["cenas"].items():
        assert db_max(tts.Path(c["wav"])) > -30, f"cena {cid} saiu muda"


def test_buracos_de_fala_detecta_fala_que_para_no_meio(tmp_path):
    """O Gemini às vezes para de falar e devolve o resto com chiado; isso precisa ser detectado."""
    cortado = concatenar(tmp_path / "c.wav", fala_sintetica(tmp_path / "f.wav", 8), chiado(tmp_path / "n.wav", 20))
    buracos = tts.buracos_de_fala(cortado)
    assert buracos and 7.5 <= buracos[0][0] <= 9.5


def test_buracos_de_fala_aceita_fala_continua(tmp_path):
    assert tts.buracos_de_fala(fala_sintetica(tmp_path / "f.wav", 20)) == []


def test_gemini_cortado_refaz_com_um_pedido_por_cena(tmp_path, cfg, roteiro_curto, gemini_falso):
    """Pedido único com fala só nos primeiros 8 s: refaz no Gemini cena a cena (mesma voz), não no edge-tts."""
    cortado = concatenar(tmp_path / "c.wav", fala_sintetica(tmp_path / "f.wav", 8), chiado(tmp_path / "n.wav", 22))
    cena = fala_sintetica(tmp_path / "cena.wav", 10)
    gemini_falso["resposta"] = lambda texto, n: cortado if n == 1 else cena
    r = tts.narrar(roteiro_curto, cfg, tmp_path / "out")
    assert len(gemini_falso["pedidos"]) == 1 + 3
    assert r["voz"]["provedor"] == "gemini"


def test_pedido_ao_gemini_leva_direcao_e_emocao_da_cena(tmp_path, cfg, roteiro_curto, gemini_falso):
    """Narração mais humana: notas de direção + [emoção] por cena antes da TRANSCRIÇÃO."""
    fala = fala_sintetica(tmp_path / "fala.wav", 30)
    gemini_falso["resposta"] = lambda texto, n: fala
    tts.narrar(roteiro_curto, cfg, tmp_path / "out")
    pedido = gemini_falso["pedidos"][0]
    assert "TRANSCRIÇÃO:" in pedido
    assert pedido.count("[empolgado]") == 3


def test_sem_direcao_manda_so_o_texto(tmp_path, cfg, roteiro_curto, gemini_falso):
    fala = fala_sintetica(tmp_path / "fala.wav", 30)
    gemini_falso["resposta"] = lambda texto, n: fala
    cfg["narracao"]["direcao"] = ""
    tts.narrar(roteiro_curto, cfg, tmp_path / "out")
    assert "TRANSCRIÇÃO" not in gemini_falso["pedidos"][0]


def test_dirigido_limpa_colchetes_e_aplica_pronuncia():
    txt = tts.dirigido([{"text": "GPON chegou.", "emocao": "sério [x]\nnovo"}], {"GPON": "Gêpon"}, "Narre.")
    linha = txt.split("TRANSCRIÇÃO:\n")[1]
    assert linha == "[sério  x  novo] Gêpon chegou."
