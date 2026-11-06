"""Narração: Google AI Studio (Gemini TTS) primeiro; edge-tts só se o Gemini não gerar.

Regras:
- Nunca mistura vozes: se qualquer trecho falhar no Gemini, refaz TUDO no edge-tts.
- Nenhuma instrução de estilo vai no texto (o modelo pode lê-la em voz alta).
- Menos requisições possível: um pedido por capítulo (longo) ou um só (curto).
- A chave vai no cabeçalho x-goog-api-key, nunca na URL, e nunca é impressa.
"""
from __future__ import annotations

import asyncio
import base64
import difflib
import json
import re
import time
import urllib.error
import urllib.request
import wave
from pathlib import Path

from .util import chave, duracao, log, nota, run, tokens

BASE = "https://generativelanguage.googleapis.com/v1beta"


class PularModelo(Exception):
    pass


# ---------------------------------------------------------------- Gemini
def _gemini(method: str, path: str, key: str, body: dict | None = None, timeout=600):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(BASE + path, data=data, method=method,
                                 headers={"x-goog-api-key": key, "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode())
        except Exception:
            return e.code, {}


def modelos_tts(key: str, prefs: list[str]) -> list[str]:
    st, js = _gemini("GET", "/models?pageSize=1000", key)
    if st != 200:
        raise RuntimeError(f"não consegui listar modelos do Gemini (HTTP {st})")
    nomes = [m["name"] for m in js.get("models", [])
             if "tts" in m["name"] and "generateContent" in m.get("supportedGenerationMethods", [])]
    ordem = []
    for p in prefs:
        for n in nomes:
            if p in n and n not in ordem:
                ordem.append(n)
    ordem += [n for n in nomes if n not in ordem]
    return ordem


def _retry_delay(js) -> float | None:
    for d in js.get("error", {}).get("details", []):
        rd = d.get("retryDelay")
        if rd:
            m = re.match(r"([\d.]+)s", rd)
            if m:
                return float(m.group(1))
    return None


def _cota_diaria_ou_zero(js) -> bool:
    txt = json.dumps(js)
    return ("PerDay" in txt) or ('"quotaValue": "0"' in txt) or ("limit: 0" in txt)


def gemini_trecho(key: str, model: str, texto: str, voz: str, out_wav: Path) -> float:
    body = {
        "contents": [{"parts": [{"text": texto}]}],
        "generationConfig": {"responseModalities": ["AUDIO"],
                             "speechConfig": {"voiceConfig": {"prebuiltVoiceConfig": {"voiceName": voz}}}},
    }
    for tentativa in range(4):
        st, js = _gemini("POST", f"/{model}:generateContent", key, body)
        if st == 200:
            try:
                part = js["candidates"][0]["content"]["parts"][0]["inlineData"]
            except (KeyError, IndexError):
                raise PularModelo("resposta sem áudio")
            pcm = base64.b64decode(part["data"])
            m = re.search(r"rate=(\d+)", part.get("mimeType", ""))
            rate = int(m.group(1)) if m else 24000
            with wave.open(str(out_wav), "wb") as w:
                w.setnchannels(1); w.setsampwidth(2); w.setframerate(rate); w.writeframes(pcm)
            return len(pcm) / 2 / rate
        if st == 429:
            if _cota_diaria_ou_zero(js):
                raise PularModelo("cota diária esgotada ou zero no plano grátis (429)")
            espera = _retry_delay(js) or 30
            if espera > 90:
                raise PularModelo(f"429 pedindo espera de {espera:.0f}s")
            log(f"  429 no {model}; aguardando {espera:.0f}s")
            time.sleep(espera + 2)
            continue
        if st in (500, 502, 503, 504):
            time.sleep(10 * (tentativa + 1))
            continue
        raise PularModelo(f"HTTP {st}: {js.get('error', {}).get('message', '')[:160]}")
    raise PularModelo("muitas tentativas")


# ---------------------------------------------------------------- edge-tts
def edge_trecho(texto: str, voz: str, rate: str, out_mp3: Path):
    import edge_tts

    async def go():
        await edge_tts.Communicate(texto, voz, rate=rate).save(str(out_mp3))
    for t in range(4):
        try:
            asyncio.run(go())
            return
        except Exception as e:  # rede instável
            log(f"  edge-tts falhou ({e}); tentando de novo")
            time.sleep(5 * (t + 1))
    raise RuntimeError("edge-tts falhou 4 vezes")


def normalizar_wav(src: Path, dst: Path):
    run(["ffmpeg", "-v", "error", "-y", "-i", src, "-af",
         "silenceremove=start_periods=1:start_threshold=-45dB,areverse,"
         "silenceremove=start_periods=1:start_threshold=-45dB,areverse,aresample=44100",
         "-ac", "1", "-sample_fmt", "s16", dst])


# ---------------------------------------------------------------- alinhamento
_WHISPER = None


def transcrever(wav: Path, modelo: str = "small") -> list[dict] | None:
    global _WHISPER
    try:
        from faster_whisper import WhisperModel
        if _WHISPER is None:
            log(f"carregando faster-whisper '{modelo}' (CPU int8)")
            _WHISPER = WhisperModel(modelo, device="cpu", compute_type="int8")
        segs, _ = _WHISPER.transcribe(str(wav), language="pt", word_timestamps=True, vad_filter=False, beam_size=1)
        out = []
        for s in segs:
            for w in (s.words or []):
                out.append({"w": w.word.strip(), "s": float(w.start), "e": float(w.end)})
        return out
    except Exception as e:
        log(f"  whisper indisponível ({e}); usando tempo proporcional")
        return None


def alinhar(palavras: list[str], asr: list[dict] | None, dur: float):
    """Devolve (inicio, fim) de cada palavra do roteiro usando o ASR; interpola o que não casou."""
    n = len(palavras)
    chaves = ["".join(tokens(p)) for p in palavras]
    tempos: list[list[float] | None] = [None] * n
    casadas = 0
    if asr:
        ak = ["".join(tokens(a["w"])) for a in asr]
        sm = difflib.SequenceMatcher(None, chaves, ak, autojunk=False)
        for a, b, size in sm.get_matching_blocks():
            for k in range(size):
                if chaves[a + k]:
                    tempos[a + k] = [asr[b + k]["s"], asr[b + k]["e"]]
                    casadas += 1
    # interpolação por número de caracteres entre âncoras
    pesos = [max(1, len(p)) for p in palavras]
    anc = [(-1, 0.0)] + [(i, tempos[i][0]) for i in range(n) if tempos[i]] + [(n, dur)]
    for (i0, t0), (i1, t1) in zip(anc, anc[1:]):
        if i1 - i0 <= 1:
            continue
        ini = tempos[i0][1] if i0 >= 0 and tempos[i0] else t0
        tot = sum(pesos[i0 + 1:i1]) or 1
        acc = ini
        span = max(0.0, t1 - ini)
        for i in range(i0 + 1, i1):
            d = span * pesos[i] / tot
            tempos[i] = [acc, acc + d * 0.92]
            acc += d
    return tempos, casadas


# ---------------------------------------------------------------- orquestração
def _trechos(roteiro: dict) -> list[list[dict]]:
    if roteiro["formato"] == "curto":
        return [[sc for ch in roteiro["chapters"] for sc in ch["scenes"]]]
    return [ch["scenes"] for ch in roteiro["chapters"]]


def narrar(roteiro: dict, cfg: dict, pasta: Path) -> dict:
    """Gera audio/cena_{id}.wav para cada cena e devolve {id: {wav, dur, words}} + metadados."""
    ncfg = cfg["narracao"]
    aud = pasta / "audio"
    aud.mkdir(parents=True, exist_ok=True)
    trechos = _trechos(roteiro)
    textos = [" ".join(sc["text"] for sc in tr) for tr in trechos]
    provedor = ncfg.get("provedor", "auto")
    usado = None
    key = chave("GEMINI_API_KEY")

    if provedor in ("auto", "gemini"):
        if not key:
            nota("Narração: GEMINI_API_KEY não configurada; usei edge-tts.")
        else:
            try:
                modelos = modelos_tts(key, ncfg.get("gemini_modelos_preferidos", []))
            except Exception as e:
                modelos = []
                nota(f"Narração: não consegui listar modelos TTS do Gemini ({e}).")
            for m in modelos:
                log(f"Gemini TTS: tentando {m} com a voz {ncfg['gemini_voz']} ({len(textos)} pedido(s))")
                try:
                    for i, tx in enumerate(textos):
                        raw = aud / f"raw_{i}.wav"
                        d = gemini_trecho(key, m, tx, ncfg["gemini_voz"], raw)
                        wps = len(tx.split()) / max(d, 0.1)
                        log(f"  trecho {i}: {d:.1f}s, {wps:.2f} palavras/s")
                        if not 1.6 <= wps <= 4.6:
                            raise PularModelo(f"ritmo suspeito ({wps:.2f} palavras/s): pode ter lido instrução ou cortado texto")
                    usado = {"provedor": "gemini", "modelo": m.split("/")[-1], "voz": ncfg["gemini_voz"]}
                    break
                except PularModelo as e:
                    nota(f"Narração: {m.split('/')[-1]} não serviu ({e}).")
            if not usado:
                nota("Narração: nenhum modelo Gemini TTS gerou o áudio completo; refiz tudo no edge-tts (sem misturar vozes).")
    if not usado:
        for i, tx in enumerate(textos):
            mp3 = aud / f"raw_{i}.mp3"
            edge_trecho(tx, ncfg["edge_voz"], ncfg["edge_velocidade"], mp3)
        usado = {"provedor": "edge", "voz": ncfg["edge_voz"], "velocidade": ncfg["edge_velocidade"]}
        nota(f"Narração em edge-tts ({ncfg['edge_voz']} {ncfg['edge_velocidade']}): os termos preveem uso pessoal; "
             "para monetizar, use o Gemini TTS com cota.")

    ext = "wav" if usado["provedor"] == "gemini" else "mp3"
    cenas = {}
    total_asr, total_rot = 0, 0
    for i, tr in enumerate(trechos):
        norm = aud / f"trecho_{i}.wav"
        normalizar_wav(aud / f"raw_{i}.{ext}", norm)
        dur = duracao(norm)
        palavras_cena = [sc["text"].split() for sc in tr]
        todas = [w for ws in palavras_cena for w in ws]
        asr = transcrever(norm, cfg.get("whisper_modelo", "small"))
        if asr:
            total_asr += len(asr)
            total_rot += len(todas)
        tempos, casadas = alinhar(todas, asr, dur)
        if asr:
            log(f"trecho {i}: {dur:.1f}s, {casadas}/{len(todas)} palavras casadas com o ASR")
        k = 0
        lim = []
        for ws in palavras_cena:
            lim.append((k, k + len(ws) - 1))
            k += len(ws)
        for j, sc in enumerate(tr):
            a, b = lim[j]
            ini = tempos[a][0]
            fim = tempos[b][1]
            ant = tempos[lim[j - 1][1]][1] if j else 0.0
            prox = tempos[lim[j + 1][0]][0] if j + 1 < len(tr) else dur
            c0 = max(0.0, (ant + ini) / 2 if j else 0.0, ini - 0.08)
            c1 = min(dur, (fim + prox) / 2 if j + 1 < len(tr) else dur, fim + 0.18)
            wav = aud / f"cena_{sc['id']}.wav"
            run(["ffmpeg", "-v", "error", "-y", "-i", norm, "-ss", f"{c0:.3f}", "-to", f"{c1:.3f}",
                 "-ar", "44100", "-ac", "1", "-sample_fmt", "s16", wav])
            words = [{"w": todas[q], "s": max(0.0, tempos[q][0] - c0), "e": max(0.0, tempos[q][1] - c0)} for q in range(a, b + 1)]
            cenas[sc["id"]] = {"wav": str(wav), "dur": duracao(wav), "words": words}
    if usado["provedor"] == "gemini" and total_rot and total_asr / total_rot > 1.3:
        nota(f"Narração: o Gemini falou {total_asr} palavras para {total_rot} do roteiro (leu algo a mais). Refiz no edge-tts.")
        ncfg2 = dict(ncfg, provedor="edge")
        return narrar(roteiro, dict(cfg, narracao=ncfg2), pasta)
    return {"cenas": cenas, "voz": usado}
