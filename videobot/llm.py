"""Cliente de texto do Google AI Studio (Gemini). Chave só no cabeçalho, nunca impressa."""
from __future__ import annotations

import json
import re
import time

from .tts import _cota_diaria_ou_zero, _gemini, _retry_delay
from .util import chave, log, nota

_DESCOBERTOS = None


def _modelos(cfg) -> list[str]:
    global _DESCOBERTOS
    base = [m if m.startswith("models/") else "models/" + m for m in cfg["llm"].get("modelos", [])]
    if _DESCOBERTOS is None:
        _DESCOBERTOS = []
        st, js = _gemini("GET", "/models?pageSize=1000", chave("GEMINI_API_KEY"))
        if st == 200:
            for m in js.get("models", []):
                n = m["name"]
                if ("generateContent" in m.get("supportedGenerationMethods", []) and re.search(r"gemini-[\d.]+-(pro|flash)$", n)):
                    _DESCOBERTOS.append(n)
            _DESCOBERTOS.sort(key=lambda n: [float(x) for x in re.findall(r"gemini-([\d.]+)", n)[:1] or [0]], reverse=True)
    return base + [m for m in _DESCOBERTOS if m not in base]


def gerar(prompt: str, cfg: dict, busca: bool = False, json_mode: bool = False, temperatura: float = 0.6, sistema: str = "") -> tuple[str, dict, str]:
    key = chave("GEMINI_API_KEY")
    body = {"contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": temperatura}}
    if sistema:
        body["systemInstruction"] = {"parts": [{"text": sistema}]}
    if busca:
        body["tools"] = [{"google_search": {}}]
    elif json_mode:
        body["generationConfig"]["responseMimeType"] = "application/json"
    erros = []
    for m in _modelos(cfg):
        for tentativa in range(4):
            st, js = _gemini("POST", f"/{m}:generateContent", key, body, timeout=600)
            if st == 200:
                try:
                    cand = js["candidates"][0]
                    txt = "".join(p.get("text", "") for p in cand["content"]["parts"])
                except (KeyError, IndexError):
                    erros.append(f"{m}: resposta vazia")
                    break
                return txt, cand.get("groundingMetadata", {}), m.split("/")[-1]
            if st == 429 and not _cota_diaria_ou_zero(js):
                espera = _retry_delay(js) or 20
                if espera <= 90:
                    log(f"  429 em {m}; aguardando {espera:.0f}s")
                    time.sleep(espera + 2)
                    continue
            if st in (500, 502, 503, 504):
                time.sleep(8 * (tentativa + 1))
                continue
            erros.append(f"{m.split('/')[-1]}: HTTP {st}")
            break
    raise RuntimeError("nenhum modelo de texto do Gemini respondeu: " + "; ".join(erros[-4:]))


def extrair_json(txt: str):
    t = txt.strip()
    m = re.search(r"```(?:json)?\s*(.*?)```", t, re.S)
    if m:
        t = m.group(1).strip()
    i = min([x for x in (t.find("{"), t.find("[")) if x >= 0] or [0])
    t = t[i:]
    try:
        return json.loads(t)
    except json.JSONDecodeError:
        # corta lixo depois do último fechamento
        for fim in range(len(t), 0, -1):
            if t[fim - 1] in "}]":
                try:
                    return json.loads(t[:fim])
                except json.JSONDecodeError:
                    continue
        raise


def gerar_json(prompt: str, cfg: dict, busca: bool = False, temperatura: float = 0.5, sistema: str = ""):
    ultimo = None
    for _ in range(2):
        txt, meta, modelo = gerar(prompt, cfg, busca=busca, json_mode=not busca, temperatura=temperatura, sistema=sistema)
        try:
            return extrair_json(txt), meta, modelo
        except Exception as e:
            ultimo = e
            prompt += "\n\nATENÇÃO: responda SOMENTE com JSON válido, sem texto fora dele."
    raise RuntimeError(f"o modelo não devolveu JSON válido ({ultimo})")
