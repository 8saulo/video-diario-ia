"""Utilitários dos testes: áudio sintético gerado com ffmpeg e Gemini falso (nada de rede)."""
from __future__ import annotations

import shutil
import subprocess
import sys
import wave
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from videobot import tts  # noqa: E402
from videobot.util import carregar_config  # noqa: E402


def ffmpeg(*args):
    subprocess.run(["ffmpeg", "-v", "error", "-y", *map(str, args)], check=True)


def fala_sintetica(dst: Path, seg: float, sr: int = 24000):
    """Tom com 'sílabas' (volume oscilando 4x por segundo): parece fala para o detector de energia."""
    ffmpeg("-f", "lavfi", "-i", f"sine=f=180:r={sr}:d={seg}",
           "-af", "volume='0.6*(0.5+0.5*sin(2*PI*4*t))':eval=frame", "-ac", "1", "-sample_fmt", "s16", dst)
    return dst


def chiado(dst: Path, seg: float, amp: float = 0.03, sr: int = 24000):
    ffmpeg("-f", "lavfi", "-i", f"anoisesrc=d={seg}:c=pink:a={amp}:r={sr}", "-ac", "1", "-sample_fmt", "s16", dst)
    return dst


def concatenar(dst: Path, *partes: Path):
    ffmpeg(*sum([["-i", p] for p in partes], []), "-filter_complex",
           f"concat=n={len(partes)}:v=0:a=1", "-sample_fmt", "s16", dst)
    return dst


def dur_wav(p: Path) -> float:
    with wave.open(str(p)) as w:
        return w.getnframes() / w.getframerate()


def db_max(p: Path) -> float:
    import numpy as np
    rms, _ = tts._rms_frames(p)
    return float(20 * np.log10(rms.max() + 1e-9))


@pytest.fixture
def cfg():
    return carregar_config()


@pytest.fixture
def roteiro_curto():
    """3 cenas de 30 palavras: ~10 s cada a 3 palavras/s."""
    return {"formato": "curto", "chapters": [{"title": "t", "scenes": [
        {"id": f"c{i}", "text": " ".join(["palavra"] * 30), "emocao": "empolgado"} for i in range(3)]}]}


@pytest.fixture
def gemini_falso(monkeypatch, tmp_path):
    """Troca o Gemini TTS por uma função que devolve o áudio escolhido pelo teste e guarda os pedidos."""
    estado = {"pedidos": [], "resposta": None}

    def falso(key, model, texto, voz, dst):
        estado["pedidos"].append(texto)
        src = estado["resposta"](texto, len(estado["pedidos"]))
        shutil.copy(src, dst)
        return dur_wav(Path(dst))

    monkeypatch.setattr(tts, "modelos_tts", lambda k, p: ["models/falso-tts"])
    monkeypatch.setattr(tts, "gemini_trecho", falso)
    monkeypatch.setattr(tts, "chave", lambda nome: "x")
    monkeypatch.setattr(tts, "transcrever", lambda *a, **k: None)  # sem Whisper nos testes rápidos
    return estado
