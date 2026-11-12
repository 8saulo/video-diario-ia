"""Cliente de texto com vários provedores grátis (Groq e OpenRouter; Gemini é opcional).

A ordem vem de `llm.ordem` no config.yml. Para cada provedor com chave no ambiente, o script lista os
modelos disponíveis, põe primeiro os de `llm.<provedor>.modelos` (trechos do nome) e tenta um por um.
Se um modelo estoura a cota (429), pede demais (413) ou não existe (404), passa para o próximo.
Chaves só nos cabeçalhos, nunca impressas.
"""
from __future__ import annotations

import json
import os
import re
import threading
import time

import requests

from .util import chave, log, nota

# provedores compatíveis com a API da OpenAI (/chat/completions e /models)
PROVEDORES = {
    "groq": {"base": "https://api.groq.com/openai/v1", "env": "GROQ_API_KEY", "titulo": "Groq"},
    "openrouter": {"base": "https://openrouter.ai/api/v1", "env": "OPENROUTER_API_KEY", "titulo": "OpenRouter"},
    "gemini": {"base": "", "env": "GEMINI_API_KEY", "titulo": "Google Gemini"},
}
# modelos que não servem para escrever texto
NAO_TEXTO = re.compile(r"whisper|tts|guard|embed|image|vision|audio|transcri|playai|orpheus|rerank|moderation|compound|banana|live|robotics|computer", re.I)

_lock = threading.Lock()
_modelos_cache: dict[str, list[str]] = {}
_fora: set[str] = set()  # "provedor/modelo" que já falharam de vez nesta execução


def ordem(cfg: dict) -> list[str]:
    o = (cfg.get("llm") or {}).get("ordem") or ["groq", "openrouter"]
    return [p for p in o if p in PROVEDORES]


def disponiveis(cfg: dict) -> list[str]:
    """Provedores da ordem que têm chave configurada."""
    return [p for p in ordem(cfg) if chave(PROVEDORES[p]["env"])]


# ---------------------------------------------------------------- listar modelos
def listar_modelos(prov: str, forcar: bool = False) -> list[str]:
    """Modelos de texto que a chave do provedor enxerga (cache por execução)."""
    with _lock:
        if prov in _modelos_cache and not forcar:
            return _modelos_cache[prov]
    key = chave(PROVEDORES[prov]["env"])
    nomes: list[str] = []
    if key:
        try:
            if prov == "gemini":
                from .tts import _gemini
                st, js = _gemini("GET", "/models?pageSize=1000", key, timeout=30)
                if st == 200:
                    nomes = [m["name"].split("/")[-1] for m in js.get("models", [])
                             if "generateContent" in m.get("supportedGenerationMethods", []) and m["name"].split("/")[-1].startswith("gemini")]
            else:
                hd = {"Authorization": f"Bearer {key}"}
                r = requests.get(PROVEDORES[prov]["base"] + "/models", headers=hd, timeout=30)
                if r.status_code == 200:
                    for m in r.json().get("data", []):
                        mid = m.get("id", "")
                        if prov == "openrouter":
                            # só os gratuitos e que aceitam texto
                            preco = m.get("pricing") or {}
                            gratis = mid.endswith(":free") or (str(preco.get("prompt")) in ("0", "0.0") and str(preco.get("completion")) in ("0", "0.0"))
                            mods = ((m.get("architecture") or {}).get("output_modalities") or ["text"])
                            if not gratis or "text" not in mods:
                                continue
                        if m.get("active") is False:
                            continue
                        nomes.append(mid)
        except Exception as e:  # rede, JSON etc.: tenta de novo na próxima chamada
            log(f"  não consegui listar os modelos do {PROVEDORES[prov]['titulo']} ({str(e)[:80]})")
            return []
    nomes = [n for n in nomes if not NAO_TEXTO.search(n)]
    with _lock:
        if nomes:  # lista vazia não fica em cache (falha passageira não trava a execução)
            _modelos_cache[prov] = nomes
    return nomes


def _ordenar(prov: str, cfg: dict) -> list[str]:
    prefs = list(((cfg.get("llm") or {}).get(prov) or {}).get("modelos") or [])
    nomes = listar_modelos(prov)
    if not nomes:  # sem lista: tenta os preferidos como estão escritos
        return [p for p in prefs if f"{prov}/{p}" not in _fora]
    out = []
    for p in prefs:
        for n in nomes:
            if (n == p or p in n) and n not in out:
                out.append(n)
    if ((cfg.get("llm") or {}).get(prov) or {}).get("so_preferidos"):
        resto = []
    else:
        resto = sorted((n for n in nomes if n not in out), key=_tamanho, reverse=True)
    return [m for m in out + resto if f"{prov}/{m}" not in _fora]


def _tamanho(nome: str) -> float:
    """Ordena os modelos que sobraram do maior para o menor (pelo 'NNb' no nome)."""
    m = re.findall(r"(\d+(?:\.\d+)?)b\b", nome.lower())
    return max(float(x) for x in m) if m else 0.0


# ---------------------------------------------------------------- chamadas
def _limpar(txt: str) -> str:
    return re.sub(r"(?is)<think>.*?</think>", "", txt or "").strip()


def _espera(r) -> float:
    for h in ("retry-after", "x-ratelimit-reset-requests", "x-ratelimit-reset-tokens"):
        v = r.headers.get(h)
        if not v:
            continue
        m = re.fullmatch(r"(?:(\d+)m)?(\d+(?:\.\d+)?)s?", v.strip())
        if m:
            return float(m.group(1) or 0) * 60 + float(m.group(2))
    return 0.0


def _openai(prov: str, modelo: str, msgs: list, temperatura: float, max_tokens: int) -> tuple[int, str, float, str]:
    key = chave(PROVEDORES[prov]["env"])
    hd = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    if prov == "openrouter":
        hd.update({"HTTP-Referer": "https://github.com/8saulo/video-diario-ia", "X-Title": "video-diario-ia"})
    body = {"model": modelo, "messages": msgs, "temperature": temperatura, "max_tokens": max_tokens}
    # modelos que "pensam" antes de responder podem gastar todo o max_tokens pensando e devolver a resposta vazia
    if prov == "openrouter":
        body["reasoning"] = {"effort": "low", "exclude": True}
    elif prov == "groq" and "gpt-oss" in modelo:
        body["reasoning_effort"] = "low"
    try:
        r = requests.post(PROVEDORES[prov]["base"] + "/chat/completions", headers=hd, json=body, timeout=float(os.environ.get("VIDEOBOT_TIMEOUT_LLM", 150)))
    except requests.RequestException as e:
        return 0, "", 0.0, str(e)[:120]
    if r.status_code != 200:
        try:
            err = r.json().get("error") or {}
            msg = err.get("message", "") if isinstance(err, dict) else str(err)
        except Exception:
            msg = r.text[:200]
        return r.status_code, "", _espera(r), msg[:200]
    try:
        js = r.json()
        ch = js["choices"][0]
        txt = ch["message"].get("content") or ""
    except Exception:
        return 200, "", 0.0, "resposta vazia"
    if not _limpar(txt):
        motivo = "gastou o limite pensando" if ch.get("finish_reason") == "length" else f"fim: {ch.get('finish_reason')}"
        return 200, "", 0.0, f"resposta vazia ({motivo})"
    return 200, _limpar(txt), 0.0, ""


def _gemini_texto(modelo: str, prompt: str, sistema: str, temperatura: float) -> tuple[int, str, float, str]:
    from .tts import _gemini, _cota_diaria_ou_zero, _retry_delay
    body = {"contents": [{"role": "user", "parts": [{"text": prompt}]}], "generationConfig": {"temperature": temperatura}}
    if sistema:
        body["systemInstruction"] = {"parts": [{"text": sistema}]}
    st, js = _gemini("POST", f"/models/{modelo}:generateContent", chave("GEMINI_API_KEY"), body, timeout=300)
    if st == 200:
        try:
            return 200, "".join(p.get("text", "") for p in js["candidates"][0]["content"]["parts"]), 0.0, ""
        except (KeyError, IndexError):
            return 200, "", 0.0, "resposta vazia"
    espera = 0.0 if st != 429 or _cota_diaria_ou_zero(js) else (_retry_delay(js) or 20)
    return st, "", espera, ((js or {}).get("error") or {}).get("message", "")[:200]


def gerar(prompt: str, cfg: dict, temperatura: float = 0.6, sistema: str = "", max_tokens: int | None = None) -> tuple[str, str]:
    """Devolve (texto, "provedor/modelo"). Tenta provedores e modelos em ordem até um responder."""
    lcfg = cfg.get("llm") or {}
    max_tokens = max_tokens or int(lcfg.get("max_tokens", 8000))
    espera_max = float(lcfg.get("espera_max_s", 65))
    provs = disponiveis(cfg)
    if not provs:
        raise RuntimeError("nenhum provedor de texto com chave configurada (" +
                           ", ".join(PROVEDORES[p]["env"] for p in ordem(cfg)) + ")")
    msgs = ([{"role": "system", "content": sistema}] if sistema else []) + [{"role": "user", "content": prompt}]
    rodadas = int(lcfg.get("rodadas", 3))
    todos = []
    for rodada in range(rodadas):
        txt, modelo, erros, so_cota = _rodada(prov_lista=provs, cfg=cfg, lcfg=lcfg, prompt=prompt, sistema=sistema, msgs=msgs,
                                             temperatura=temperatura, max_tokens=max_tokens, espera_max=espera_max)
        if txt:
            return txt, modelo
        todos += erros
        if rodada + 1 < rodadas and so_cota:
            # todos recusaram por limite por minuto ou sobrecarga: espera o limite zerar e tenta a lista de novo
            log(f"  nenhum modelo respondeu (limite por minuto/sobrecarga); nova rodada em 60s ({rodada + 2}/{rodadas})")
            time.sleep(60)
            continue
        break
    raise RuntimeError("nenhum modelo de texto respondeu: " + "; ".join(todos[-5:]))


def _cota_do_dia(msg: str) -> bool:
    return bool(re.search(r"per[- ]day|daily|per day|quota|tokens per day|TPD|RPD", msg or "", re.I))


def _rodada(prov_lista, cfg, lcfg, prompt, sistema, msgs, temperatura, max_tokens, espera_max):
    erros, so_cota = [], True
    for prov in prov_lista:
        for m in _ordenar(prov, cfg)[: int(lcfg.get("modelos_por_provedor", 4))]:
            st, txt, espera, msg = _tentar(prov, m, prompt, sistema, msgs, temperatura, max_tokens, espera_max)
            if st == 200 and txt:
                return txt, f"{prov}/{m}", erros, False
            erros.append(f"{prov}/{m}: HTTP {st}{' ' + msg[:70] if msg else ''}")
            grande = st == 413 or (st == 400 and re.search(r"reduce the length|context|too long|too large", msg or "", re.I))
            passageiro = (st == 429 and not (espera > espera_max or _cota_do_dia(msg))) or st in (0, 500, 502, 503, 504)                 or (st == 200 and "pensando" in (msg or "")) or grande
            if not passageiro:
                so_cota = False
            # 413/400 de tamanho = pedido grande demais para ESTE pedido; o modelo ainda serve para pedidos menores.
            # 429 sem tempo de espera só tira o modelo da execução se for a cota do dia (sobrecarga é passageira).
            if (st in (400, 404) and not grande) or (st == 429 and (espera > espera_max or _cota_do_dia(msg))):
                with _lock:
                    _fora.add(f"{prov}/{m}")
            if st == 401 or (st == 403 and prov != "openrouter"):
                nota(f"{PROVEDORES[prov]['titulo']}: a chave foi recusada (HTTP {st}). Confira {PROVEDORES[prov]['env']}.")
                break  # chave recusada: não adianta tentar outros modelos do mesmo provedor
    return "", "", erros, so_cota


def _tentar(prov, m, prompt, sistema, msgs, temperatura, max_tokens, espera_max):
    """Até 3 tentativas no mesmo modelo: espera curtas de 429 e erros de servidor passageiros."""
    for tentativa in range(3):
        if prov == "gemini":
            st, txt, espera, msg = _gemini_texto(m, prompt, sistema, temperatura)
        else:
            st, txt, espera, msg = _openai(prov, m, msgs, temperatura, max_tokens)
        if st == 200 and txt:
            return st, txt, espera, msg
        teto = re.search(r"max_(?:completion_)?tokens`? must be (?:less than or equal to|<=) `?(\d+)", msg or "")
        if st == 400 and teto and int(teto.group(1)) < max_tokens and tentativa < 2:
            max_tokens = int(teto.group(1))  # o modelo aceita respostas menores: refaz dentro do limite dele
            continue
        if st == 429 and 0 < espera <= espera_max and tentativa < 2:
            log(f"  429 em {prov}/{m}; aguardando {espera:.0f}s")
            time.sleep(espera + 1)
            continue
        if st in (0, 500, 502, 503, 504) and tentativa < 2:
            time.sleep(6 * (tentativa + 1))
            continue
        return st, txt, espera, msg
    return st, txt, espera, msg


_visao_cache: list[str] = []


def _modelos_visao() -> list[str]:
    """Modelos grátis do OpenRouter que aceitam imagem (a lista de texto exclui os de visão de propósito)."""
    if not _visao_cache:
        try:
            r = requests.get(PROVEDORES["openrouter"]["base"] + "/models", timeout=30,
                             headers={"Authorization": f"Bearer {chave(PROVEDORES['openrouter']['env'])}"})
            for m in r.json().get("data", []):
                ent = (m.get("architecture") or {}).get("input_modalities") or []
                if m.get("id", "").endswith(":free") and "image" in ent:
                    _visao_cache.append(m["id"])
        except Exception as e:
            log(f"  não consegui listar os modelos de visão ({str(e)[:80]})")
    return list(_visao_cache)


def gerar_visao_json(prompt: str, imagens: list[str], cfg: dict, max_tokens: int = 600):
    """Pergunta a um modelo grátis que enxerga imagem (OpenRouter) olhando as imagens (URLs). Devolve (obj, modelo).
    Usa llm.visao.modelos (trechos do nome) em ordem; levanta RuntimeError se nenhum responder."""
    vcfg = (cfg.get("llm") or {}).get("visao") or {}
    if not chave(PROVEDORES["openrouter"]["env"]):
        raise RuntimeError("sem OPENROUTER_API_KEY para os modelos de visão")
    prefs = list(vcfg.get("modelos") or ["gemma-4-31b", "nemotron-3.5-super-vl", "gemma-4-26b"])
    nomes = _modelos_visao()
    modelos = [n for p in prefs for n in nomes if p in n and f"openrouter/{n}" not in _fora]
    conteudo = [{"type": "text", "text": prompt}] + [{"type": "image_url", "image_url": {"url": u}} for u in imagens]
    msgs = [{"role": "user", "content": conteudo}]
    erros = []
    modelos += [n for n in nomes if n not in modelos and f"openrouter/{n}" not in _fora]  # depois, os outros de visão
    for m in list(dict.fromkeys(modelos))[:5]:
        st, txt, espera, msg = _tentar("openrouter", m, prompt, "", msgs, 0.1, max_tokens, float((cfg.get("llm") or {}).get("espera_max_s", 65)))
        if st == 200 and txt:
            try:
                return extrair_json(txt), f"openrouter/{m}"
            except Exception as e:
                erros.append(f"{m}: JSON inválido ({str(e)[:40]})")
                continue
        erros.append(f"{m}: HTTP {st} {msg[:60]}")
    raise RuntimeError("nenhum modelo de visão respondeu: " + "; ".join(erros[-3:]))


def extrair_json(txt: str):
    t = _limpar(txt)
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


def gerar_json(prompt: str, cfg: dict, temperatura: float = 0.5, sistema: str = "", max_tokens: int | None = None):
    """Devolve (objeto, {}, "provedor/modelo"). O {} mantém a assinatura antiga (metadados de busca)."""
    ultimo = None
    for _ in range(2):
        txt, modelo = gerar(prompt, cfg, temperatura=temperatura, sistema=sistema, max_tokens=max_tokens)
        try:
            return extrair_json(txt), {}, modelo
        except Exception as e:
            ultimo = e
            prompt += "\n\nATENÇÃO: responda SOMENTE com JSON válido, sem texto fora dele."
    raise RuntimeError(f"o modelo não devolveu JSON válido ({ultimo})")
