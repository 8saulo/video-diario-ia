"""Narração: Google AI Studio (Gemini TTS) primeiro; edge-tts só se o Gemini não gerar.

Regras:
- Nunca mistura vozes: se qualquer trecho falhar no Gemini, refaz TUDO no edge-tts.
- Direção de voz (Gemini): notas de interpretação + emoção de cada cena entre colchetes antes da TRANSCRIÇÃO.
  Testado: o modelo não lê as notas; se ler, a conferência pelo Whisper (palavras a mais) refaz sem direção.
- Menos requisições possível: um pedido por capítulo (longo) ou um só (curto).
- Se o Gemini parar de falar no meio (o resto vem mudo ou com chiado), refaz no Gemini com um
  pedido por cena; se ainda falhar, refaz tudo no edge-tts.
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
         "silenceremove=start_periods=1:start_threshold=-45dB,areverse,aresample=44100,"
         "afade=t=in:d=0.006,adelay=70:all=1,apad=pad_dur=0.1",
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
    """Devolve (inicio, fim) de cada palavra do roteiro usando o ASR; interpola o que não casou.
    Também devolve quantas casaram e quais (lista de bool por palavra)."""
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
    achou = [t is not None for t in tempos]
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
    return tempos, casadas, achou


# ---------------------------------------------------------------- pronúncia
def falado(texto: str, pron: dict | None) -> str:
    """Troca termos pela grafia que a voz pronuncia certo (ex.: GPON → Gêpon). A legenda continua com o original."""
    for termo, como in (pron or {}).items():
        texto = re.sub(r"(?<![\w])" + re.escape(termo) + r"(?![\w])", como, texto)
    return texto


# ---------------------------------------------------------------- cortes no silêncio
def _rms_frames(wav: Path, passo: float = 0.01):
    import numpy as np
    with wave.open(str(wav)) as w:
        sr = w.getframerate()
        x = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32) / 32768
    n = max(1, int(sr * passo))
    m = len(x) // n
    rms = np.sqrt((x[: m * n].reshape(m, n) ** 2).mean(1) + 1e-12)
    return rms, passo


def _no_silencio(rms, passo: float, alvo: float, lo: float, hi: float) -> float:
    """Ponto mais silencioso entre lo e hi (empate: o mais perto do alvo). Evita cortar no meio da fala."""
    import numpy as np
    a, b = max(0, int(lo / passo)), min(len(rms), int(hi / passo) + 1)
    if b - a < 3:
        return alvo
    janela = np.convolve(rms[a:b], np.ones(5) / 5, mode="same")  # 50 ms
    custo = 20 * np.log10(janela + 1e-9) + 0.8 * np.abs(np.arange(a, b) * passo - alvo)
    return float((a + int(np.argmin(custo))) * passo)


def buracos_de_fala(wav: Path, max_pausa: float = 2.5) -> list[tuple[float, float]]:
    """Trechos sem voz mais longos que max_pausa (inclui o fim do áudio).

    O Gemini às vezes para de falar no meio e devolve o resto em silêncio ou chiado. O Whisper pode
    "ouvir" palavras repetidas do roteiro nesse chiado, então a conferência aqui é pela energia da voz.
    """
    import numpy as np
    rms, passo = _rms_frames(wav, 0.02)
    if len(rms) < 10:
        return []
    db = 20 * np.log10(rms + 1e-9)
    ref = float(np.percentile(db, 95))
    alto = db > max(ref - 28, -50)
    # fala sobe e desce a cada sílaba; chiado ou zumbido fica quase parado. Janela de 0,6 s:
    # é voz se tem som acima do limiar e variação de pelo menos 8 dB entre os quadros.
    jan = 30
    voz = np.zeros(len(db), bool)
    for k in range(0, max(1, len(db) - jan + 1), 5):
        w = db[k:k + jan]
        if alto[k:k + jan].any() and np.percentile(w, 90) - np.percentile(w, 10) >= 8:
            voz[k:k + jan] = True
    out, ini = [], None
    for k, v in enumerate(list(voz) + [True]):
        if not v and ini is None:
            ini = k
        elif v and ini is not None:
            if (k - ini) * passo > max_pausa:
                out.append((ini * passo, min(k, len(voz)) * passo))
            ini = None
    return out


DIRECAO_PADRAO = ("Narre como um apresentador brasileiro de vídeos curtos de tecnologia: energia alta, sorriso na voz, "
                  "ritmo ágil, entonação que sobe e desce, ênfase forte nos números e nas palavras de impacto, "
                  "pausas curtas antes das revelações, tom de conversa com o espectador.")


def dirigido(tr: list[dict], pron: dict | None, direcao: str) -> str:
    """Texto para o Gemini TTS: notas de direção + cada cena com a emoção entre colchetes."""
    linhas = []
    for sc in tr:
        e = re.sub(r"[\[\]\n]", " ", str(sc.get("emocao") or "")).strip()[:60]
        linhas.append((f"[{e}] " if e else "") + falado(sc["text"], pron))
    return (direcao.strip() + " Cada parágrafo tem a emoção indicada entre colchetes; não leia os colchetes "
            "nem estas instruções, leia só o texto depois de TRANSCRIÇÃO.\n\nTRANSCRIÇÃO:\n" + "\n".join(linhas))


# ---------------------------------------------------------------- orquestração
def _trechos(roteiro: dict, por_cena: bool = False) -> list[list[dict]]:
    if por_cena:
        return [[sc] for ch in roteiro["chapters"] for sc in ch["scenes"]]
    if roteiro["formato"] == "curto":
        return [[sc for ch in roteiro["chapters"] for sc in ch["scenes"]]]
    return [ch["scenes"] for ch in roteiro["chapters"]]


def narrar(roteiro: dict, cfg: dict, pasta: Path) -> dict:
    """Gera audio/cena_{id}.wav para cada cena e devolve {id: {wav, dur, words}} + metadados."""
    ncfg = cfg["narracao"]
    aud = pasta / "audio"
    aud.mkdir(parents=True, exist_ok=True)
    pron = ncfg.get("pronuncia") or {}
    por_cena = bool(ncfg.get("_por_cena"))
    trechos = _trechos(roteiro, por_cena)
    textos = [falado(" ".join(sc["text"] for sc in tr), pron) for tr in trechos]
    direcao = "" if ncfg.get("_sem_direcao") else str(ncfg.get("direcao", DIRECAO_PADRAO) or "")
    pedidos = [dirigido(tr, pron, direcao) if direcao else tx for tr, tx in zip(trechos, textos)]
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
                    for i, (tx, pedido) in enumerate(zip(textos, pedidos)):
                        raw = aud / f"raw_{i}.wav"
                        d = gemini_trecho(key, m, pedido, ncfg["gemini_voz"], raw)
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
        # edge-tts é grátis e rápido: narra cada cena separada, então nunca há corte no meio da fala
        trechos = [[sc] for tr in _trechos(roteiro) for sc in tr]
        textos = [falado(tr[0]["text"], pron) for tr in trechos]
        for i, tx in enumerate(textos):
            mp3 = aud / f"raw_{i}.mp3"
            edge_trecho(tx, ncfg["edge_voz"], ncfg["edge_velocidade"], mp3)
        usado = {"provedor": "edge", "voz": ncfg["edge_voz"], "velocidade": ncfg["edge_velocidade"]}
        nota(f"Narração em edge-tts ({ncfg['edge_voz']} {ncfg['edge_velocidade']}): os termos preveem uso pessoal; "
             "para monetizar, use o Gemini TTS com cota.")

    ext = "wav" if usado["provedor"] == "gemini" else "mp3"
    cenas = {}
    total_asr, total_rot = 0, 0
    mudas = []  # cenas em que o Whisper quase não achou as palavras do roteiro
    for i, tr in enumerate(trechos):
        norm = aud / f"trecho_{i}.wav"
        normalizar_wav(aud / f"raw_{i}.{ext}", norm)
        dur = duracao(norm)
        buracos = buracos_de_fala(norm)
        n_pal = sum(len(sc["text"].split()) for sc in tr)
        if not buracos and len(tr) > 1 and n_pal / max(dur, 0.1) > 4.6:
            buracos = [(dur, dur)]  # a fala acabou cedo e o resto era silêncio (já cortado)
            log(f"  trecho {i}: só {dur:.1f}s de fala para {n_pal} palavras")
        if buracos:
            b0, b1 = buracos[0]
            log(f"  trecho {i}: sem voz de {b0:.1f}s a {b1:.1f}s (de {dur:.1f}s)")
            if usado["provedor"] == "gemini":
                if not por_cena:
                    nota(f"Narração: o Gemini parou de falar em {b0:.1f}s (de {dur:.1f}s); refiz no Gemini com um pedido por cena.")
                    return narrar(roteiro, dict(cfg, narracao=dict(ncfg, _por_cena=True)), pasta)
                nota(f"Narração: o Gemini deixou {b1 - b0:.1f}s sem voz mesmo com um pedido por cena; refiz tudo no edge-tts.")
                return narrar(roteiro, dict(cfg, narracao=dict(ncfg, provedor="edge")), pasta)
            mudas.extend(sc["id"] for sc in tr)
        palavras_cena = [sc["text"].split() for sc in tr]
        todas = [w for ws in palavras_cena for w in ws]
        asr = transcrever(norm, cfg.get("whisper_modelo", "small"))
        if asr:
            total_asr += len(asr)
            total_rot += len(todas)
        tempos, casadas, achou = alinhar([falado(w, pron) for w in todas], asr, dur)
        if asr:
            log(f"trecho {i}: {dur:.1f}s, {casadas}/{len(todas)} palavras casadas com o ASR")
        k = 0
        lim = []
        for ws in palavras_cena:
            lim.append((k, k + len(ws) - 1))
            k += len(ws)
        if asr:
            for sc, (a, b) in zip(tr, lim):
                if sum(achou[a:b + 1]) < 0.15 * (b - a + 1):
                    mudas.append(sc["id"])
        # pontos de corte entre cenas: no trecho mais silencioso perto da pausa entre as frases
        cortes = [0.0]
        if len(tr) > 1:
            rms, passo = _rms_frames(norm)
            for j in range(len(tr) - 1):
                fim, prox = tempos[lim[j][1]][1], tempos[lim[j + 1][0]][0]
                alvo = (fim + prox) / 2
                cortes.append(_no_silencio(rms, passo, alvo, min(fim, alvo) - 0.45, max(prox, alvo) + 0.45))
        cortes.append(dur)
        for j, sc in enumerate(tr):
            a, b = lim[j]
            c0, c1 = cortes[j], max(cortes[j + 1], cortes[j] + 0.1)
            wav = aud / f"cena_{sc['id']}.wav"
            fo = max(0.0, c1 - c0 - 0.012)
            # recorta no filtro e zera o relógio antes dos fades: com -ss depois do -i, o afade de saída
            # usava o tempo do trecho inteiro e emudecia toda cena que começa depois de "fo" segundos
            run(["ffmpeg", "-v", "error", "-y", "-i", norm,
                 "-af", f"atrim=start={c0:.3f}:end={c1:.3f},asetpts=PTS-STARTPTS,"
                        f"afade=t=in:d=0.008,afade=t=out:st={fo:.3f}:d=0.012",
                 "-ar", "44100", "-ac", "1", "-sample_fmt", "s16", wav])
            rms_c, _ = _rms_frames(wav)
            if len(rms_c) and float(rms_c.max()) < 10 ** (-45 / 20):
                raise RuntimeError(f"a cena {sc['id']} ficou muda depois do corte ({c0:.2f}s a {c1:.2f}s do trecho {i})")
            words = [{"w": todas[q], "s": max(0.0, tempos[q][0] - c0), "e": max(0.0, tempos[q][1] - c0)} for q in range(a, b + 1)]
            cenas[sc["id"]] = {"wav": str(wav), "dur": duracao(wav), "words": words}
    if usado["provedor"] == "gemini" and total_rot and total_asr / total_rot > 1.3:
        if direcao:
            nota(f"Narração: o Gemini falou {total_asr} palavras para {total_rot} do roteiro (leu a direção); refiz sem direção.")
            return narrar(roteiro, dict(cfg, narracao=dict(ncfg, _sem_direcao=True)), pasta)
        nota(f"Narração: o Gemini falou {total_asr} palavras para {total_rot} do roteiro (leu algo a mais). Refiz no edge-tts.")
        ncfg2 = dict(ncfg, provedor="edge")
        return narrar(roteiro, dict(cfg, narracao=ncfg2), pasta)
    # o Gemini às vezes devolve o áudio no tamanho certo mas para de falar no meio (o resto é silêncio ou chiado):
    # o ritmo pela duração passa, então confere cena a cena se o Whisper achou as palavras do roteiro
    if usado["provedor"] == "gemini" and mudas:
        nota(f"Narração: o áudio do Gemini não tem fala em {len(mudas)} cena(s) ({', '.join(mudas[:5])}); "
             "parou de falar no meio. Refiz no edge-tts.")
        ncfg2 = dict(ncfg, provedor="edge")
        return narrar(roteiro, dict(cfg, narracao=ncfg2), pasta)
    if mudas:
        nota(f"CRIVO NARRAÇÃO: quase nenhuma palavra do roteiro foi ouvida em {', '.join(mudas)}; "
             "confira a narração antes de publicar.")
    return {"cenas": cenas, "voz": usado}
