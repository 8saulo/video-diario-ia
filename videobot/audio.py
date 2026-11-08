"""Mixagem: narração + trilha e efeitos 100% sintetizados em código + loudnorm em 2 passes."""
from __future__ import annotations

import json
import re
import subprocess
import wave
from pathlib import Path

import numpy as np

from .util import log, nota, run

SR = 44100


def ler_wav(p) -> np.ndarray:
    with wave.open(str(p)) as w:
        n = w.getnframes()
        x = np.frombuffer(w.readframes(n), dtype=np.int16).astype(np.float32) / 32768.0
        if w.getnchannels() == 2:
            x = x.reshape(-1, 2).mean(axis=1)
        if w.getframerate() != SR:
            idx = np.linspace(0, len(x) - 1, int(len(x) * SR / w.getframerate()))
            x = np.interp(idx, np.arange(len(x)), x).astype(np.float32)
    return x


def escrever_wav(p, x: np.ndarray, canais=1):
    y = np.clip(x, -1, 1)
    y = (y * 32767).astype(np.int16)
    with wave.open(str(p), "wb") as w:
        w.setnchannels(canais); w.setsampwidth(2); w.setframerate(SR); w.writeframes(y.tobytes())


def _nota(midi: float) -> float:
    return 440.0 * 2 ** ((midi - 69) / 12)


def trilha(dur: float, seed: int = 7) -> np.ndarray:
    """Pad ambiente + arpejo suave + pulso grave. Am–F–C–G a 84 bpm."""
    n = int(dur * SR)
    out = np.zeros(n, np.float32)
    bpm = 84
    beat = 60 / bpm
    bar = beat * 4
    acordes = [[57, 60, 64, 69], [53, 57, 60, 65], [48, 55, 60, 64], [55, 59, 62, 67]]
    rng = np.random.default_rng(seed)
    t_bar = np.arange(int(bar * SR) + int(SR * 1.5)) / SR
    k = 0
    pos = 0.0
    while pos < dur:
        ac = acordes[k % 4]
        L = min(len(t_bar), n - int(pos * SR))
        if L <= 0:
            break
        t = t_bar[:L]
        env = np.minimum(1, t / 1.2) * np.clip((bar + 1.4 - t) / 1.4, 0, 1)
        pad = np.zeros(L, np.float32)
        for m in ac:
            f = _nota(m)
            for h, a in ((1, 1.0), (2, 0.18), (3, 0.06)):
                pad += a * (np.sin(2 * np.pi * f * h * t) + 0.6 * np.sin(2 * np.pi * f * h * 1.003 * t + 1.3))
        pad *= env * 0.018
        i0 = int(pos * SR)
        out[i0:i0 + L] += pad.astype(np.float32)
        # arpejo em colcheias
        for e in range(8):
            ts = pos + e * beat / 2
            if ts >= dur:
                break
            m = ac[[0, 1, 2, 3, 2, 1, 3, 2][e]] + 12
            ln = int(0.45 * SR)
            j0 = int(ts * SR)
            ln = min(ln, n - j0)
            tt = np.arange(ln) / SR
            pl = np.sin(2 * np.pi * _nota(m) * tt) * np.exp(-tt * 7) * 0.022 * (0.8 + 0.4 * rng.random())
            out[j0:j0 + ln] += pl.astype(np.float32)
        # pulso grave nos tempos 1 e 3
        for b in (0, 2):
            ts = pos + b * beat
            if ts >= dur:
                break
            ln = min(int(0.3 * SR), n - int(ts * SR))
            tt = np.arange(ln) / SR
            fq = 50 + 70 * np.exp(-tt * 25)
            kick = np.sin(2 * np.pi * np.cumsum(fq) / SR) * np.exp(-tt * 12) * 0.05
            out[int(ts * SR):int(ts * SR) + ln] += kick.astype(np.float32)
        pos += bar
        k += 1
    fade = int(min(3.0, dur / 4) * SR)
    out[:fade] *= np.linspace(0, 1, fade)
    out[-fade:] *= np.linspace(1, 0, fade)
    return out


def whoosh(seed=1) -> np.ndarray:
    rng = np.random.default_rng(seed)
    L = int(0.75 * SR)
    x = rng.standard_normal(L).astype(np.float32)
    X = np.fft.rfft(x)
    f = np.fft.rfftfreq(L, 1 / SR)
    X *= np.exp(-((np.log(f + 1) - np.log(1400)) ** 2) / 1.2)
    y = np.fft.irfft(X, L).astype(np.float32)
    t = np.arange(L) / L
    env = np.sin(np.pi * np.clip(t * 1.25, 0, 1)) ** 2
    y = y / (np.abs(y).max() + 1e-9) * env * 0.35
    return y


def pop() -> np.ndarray:
    L = int(0.09 * SR)
    t = np.arange(L) / SR
    fq = 400 + 600 * np.exp(-t * 40)
    return (np.sin(2 * np.pi * np.cumsum(fq) / SR) * np.exp(-t * 45) * 0.12).astype(np.float32)


def _envelope(x: np.ndarray, win=0.05) -> np.ndarray:
    w = int(win * SR)
    pad = (-len(x)) % w
    r = np.sqrt((np.pad(x, (0, pad)) ** 2).reshape(-1, w).mean(axis=1))
    r = r / (r.max() + 1e-9)
    # ataque rápido, soltura lenta
    sm = np.zeros_like(r)
    a = 0.0
    for i, v in enumerate(r):
        a = v if v > a else a * 0.93
        sm[i] = a
    return np.repeat(sm, w)[:len(x)]


def loudnorm(src: Path, dst: Path, I=-14.0, TP=-1.5):
    p1 = subprocess.run(["ffmpeg", "-hide_banner", "-i", str(src), "-af", f"loudnorm=I={I}:TP={TP}:LRA=11:print_format=json",
                         "-f", "null", "-"], capture_output=True, text=True)
    m = re.search(r"\{[^{}]*\"input_i\"[^{}]*\}", p1.stderr, re.S)
    if not m:
        run(["ffmpeg", "-v", "error", "-y", "-i", src, "-af", f"loudnorm=I={I}:TP={TP}:LRA=11", "-ar", str(SR), dst])
        return
    js = json.loads(m.group(0))
    af = (f"loudnorm=I={I}:TP={TP}:LRA=11:measured_I={js['input_i']}:measured_TP={js['input_tp']}:"
          f"measured_LRA={js['input_lra']}:measured_thresh={js['input_thresh']}:offset={js['target_offset']}:linear=true")
    run(["ffmpeg", "-v", "error", "-y", "-i", src, "-af", af, "-ar", str(SR), "-ac", "2", dst])


def medir(path: Path) -> dict:
    r = subprocess.run(["ffmpeg", "-hide_banner", "-i", str(path), "-af", "volumedetect,ebur128=peak=true", "-f", "null", "-"],
                       capture_output=True, text=True).stderr
    g = lambda pat: (float(re.findall(pat, r)[-1]) if re.findall(pat, r) else None)
    return {"mean_volume": g(r"mean_volume:\s*(-?[\d.]+)"), "max_volume": g(r"max_volume:\s*(-?[\d.]+)"),
            "lufs": g(r"I:\s*(-?[\d.]+) LUFS"), "true_peak": g(r"Peak:\s*(-?[\d.]+) dBFS")}


def mixar(segs: list[dict], total: float, pasta: Path, cfg: dict) -> tuple[Path, dict]:
    n = int(total * SR) + SR
    voz = np.zeros(n, np.float32)
    fx = np.zeros(n, np.float32)
    w = whoosh(); pp = pop()
    for s in segs:
        i0 = int(s["start"] * SR)
        if s.get("wav"):
            x = ler_wav(s["wav"])
            voz[i0:i0 + len(x)] += x[:n - i0]
        if cfg["visual"].get("efeitos", True):
            if s["kind"] == "chapter":
                fx[i0:i0 + len(w)] += w[:n - i0]
            elif s["start"] > 0.1:
                fx[i0:i0 + len(pp)] += pp[:n - i0] * 0.6
    mix = voz.copy()
    if cfg["visual"].get("musica", True):
        mus = trilha(n / SR)
        mus = np.pad(mus, (0, max(0, n - len(mus))))[:n]  # int(n / SR * SR) pode dar n - 1
        env = _envelope(voz)
        ganho = 1.0 - 0.62 * np.clip(env * 1.6, 0, 1)
        mix += mus[:n] * ganho
    mix += fx
    mix = mix[:int(total * SR)]
    bruto = pasta / "_mix_bruto.wav"
    escrever_wav(bruto, mix / max(1.0, float(np.abs(mix).max()) / 0.95))
    final = pasta / "_mix_ln.wav"
    loudnorm(bruto, final)
    m = medir(final)
    log(f"áudio: mean {m['mean_volume']} dB, max {m['max_volume']} dB, {m['lufs']} LUFS, pico {m['true_peak']}")
    if m["mean_volume"] is not None and not (-18 <= m["mean_volume"] <= -14):
        nota(f"CRIVO 6: mean_volume {m['mean_volume']} dB ficou fora de −18 a −14 dB.")
    return final, m
