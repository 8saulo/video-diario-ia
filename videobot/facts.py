"""Etapa 3 (parte 1): fatos com fonte, conferidos baixando a página da fonte.

"Na dúvida, corte": se a página não abre ou o número não aparece nela, o fato sai.
"""
from __future__ import annotations

import html as H
import re
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlparse

import requests

from .llm import gerar_json
from .util import log

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"
RUINS = ("medium.com", "blogspot.", "wordpress.com", "substack.com", "linkedin.com", "quora.com", "reddit.com", "youtube.com", "tiktok.com",
         "facebook.com", "x.com", "twitter.com", "instagram.com")
ESCALA = {"thousand": 1e3, "mil": 1e3, "k": 1e3, "million": 1e6, "milhão": 1e6, "milhões": 1e6, "mi": 1e6, "m": 1e6,
          "billion": 1e9, "bilhão": 1e9, "bilhões": 1e9, "bi": 1e9, "bn": 1e9, "b": 1e9,
          "trillion": 1e12, "trilhão": 1e12, "trilhões": 1e12, "tri": 1e12, "tn": 1e12, "t": 1e12}
EXTENSO = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10}


def _texto(url: str) -> str | None:
    try:
        r = requests.get(url, headers={"User-Agent": UA, "Accept-Language": "en-US,en;q=0.9,pt-BR;q=0.8"}, timeout=25, allow_redirects=True)
        if r.status_code != 200 or "html" not in r.headers.get("content-type", "html"):
            return None
        t = r.text[:4_000_000]
        t = re.sub(r"(?is)<(script|style|noscript|svg)[^>]*>.*?</\1>", " ", t)
        t = re.sub(r"(?s)<[^>]+>", " ", t)
        t = H.unescape(t).replace(" ", " ").replace(" ", " ").replace(" ", " ")
        t = re.sub(r"\s+", " ", t)
        return t if len(t) > 500 else None
    except Exception:
        return None


def _resolver(uri: str) -> str:
    try:
        r = requests.head(uri, allow_redirects=True, timeout=15, headers={"User-Agent": UA})
        return r.url
    except Exception:
        return uri


def valores(txt: str) -> set[float]:
    """Todos os números de um texto, também multiplicados pela escala escrita ao lado (1 million → 1e6)."""
    out = set()
    t = txt.lower().replace("–", "-").replace("—", "-")
    for w, v in EXTENSO.items():
        for m in re.finditer(rf"\b{w}\b(\s+(thousand|million|billion|trillion))?", t):
            out.add(float(v))
            if m.group(2):
                out.add(float(v) * ESCALA[m.group(2)])
    for m in re.finditer(r"(\d[\d,.]*\d|\d)(\s*(%|thousand|million|billion|trillion|milh[aã]o|milh[oõ]es|bilh[aã]o|bilh[oõ]es|trilh[aã]o|trilh[oõ]es|mil|bn|tn|bi|tri|mi|[kmbt])\b)?", t):
        raw = m.group(1).strip()
        cands = []
        if re.fullmatch(r"\d{1,3}(,\d{3})+(\.\d+)?", raw):
            cands.append(float(raw.replace(",", "")))
        elif re.fullmatch(r"\d{1,3}(\.\d{3})+(,\d+)?", raw):
            cands.append(float(raw.replace(".", "").replace(",", ".")))
        else:
            r2 = raw.replace(" ", "")
            for x in (r2.replace(",", "."), r2.replace(",", "")):
                try:
                    cands.append(float(x))
                except ValueError:
                    pass
        esc = ESCALA.get((m.group(3) or "").strip(), 1)
        for c in cands:
            out.add(c)
            if esc != 1:
                out.add(c * esc)
    return out


def _numero_na_pagina(num: str, pagina: str, vals_pagina: set[float]) -> bool:
    n = num.strip().lower()
    if n and n in pagina.lower():
        return True
    alvo = valores(n)
    if not alvo:
        return False
    for a in alvo:
        for v in vals_pagina:
            if a == v or (a and abs(a - v) / abs(a) < 0.005):
                return True
    return False


def _verificar(f: dict) -> dict:
    url = f.get("url") or ""
    dom = urlparse(url).netloc.lower().removeprefix("www.")
    if not url.startswith("http") or any(r in dom for r in RUINS):
        return dict(f, ok=False, motivo="fonte ausente ou não confiável")
    pg = _texto(url)
    if not pg:
        return dict(f, ok=False, motivo="página da fonte não abriu (paywall, bloqueio ou link errado)")
    vp = valores(pg)
    nums = [str(n) for n in (f.get("numeros") or []) if str(n).strip()]
    conferidos, faltando = [], []
    for n in nums:
        (conferidos if _numero_na_pagina(n, pg, vp) else faltando).append(n)
    trecho = re.sub(r"\s+", " ", (f.get("trecho") or "")).strip().lower()
    achou_trecho = len(trecho) > 25 and trecho[:60] in pg.lower()
    if faltando:
        return dict(f, ok=False, motivo="número(s) não encontrado(s) na página: " + ", ".join(faltando), dominio=dom)
    if not nums and not achou_trecho:
        return dict(f, ok=False, motivo="trecho citado não encontrado na página", dominio=dom)
    return dict(f, ok=True, conferidos=conferidos, dominio=dom)


def coletar(cand: dict, cfg: dict) -> dict:
    tema = cand["tema"]
    ref = f'Vídeo de referência (só para entender o tema; NÃO copie o conteúdo): "{cand.get("titulo")}"' if cand.get("titulo") else ""
    prompt = f"""Pesquise na web o tema: "{tema}". {ref}
Monte uma base de fatos para um vídeo brasileiro sobre {cfg['tema'].get('nicho', 'IA e tecnologia')}.

Regras:
- 14 a 22 fatos, com números verificáveis sempre que possível, dos últimos meses quando for notícia.
- Só fontes confiáveis: agências (Reuters, AP, AFP), CNBC, Bloomberg, WSJ, FT, The Verge, Ars Technica, IEEE Spectrum, Nature, sites oficiais de empresas e governos, papers; Wikipedia só como apoio. Nada de blogs de SEO, agregadores ou páginas geradas por IA.
- Inclua o contraponto (críticos, riscos, limites) e quem defende.
- "url" é a URL exata da matéria onde o número aparece (não a home do site). "numeros" são os números exatamente como escritos na página (ex.: "2.1 trillion", "75 billion", "40%", "2028"). "trecho" é uma frase curta copiada literalmente da página contendo o número (até 25 palavras, no idioma original).
- "data" é a data de publicação da matéria no formato DD/MM/AAAA.
- Se dois veículos divergem num número, use o da fonte mais confiável e diga em "obs".

Responda SOMENTE com JSON:
{{"tema_pt": "título curto do tema em PT-BR", "angulo": "ângulo do vídeo em 1 frase", "financas": true/false,
 "fatos": [{{"afirmacao": "frase em PT-BR", "numeros": ["..."], "fonte": "nome do veículo", "url": "https://...", "data": "DD/MM/AAAA", "trecho": "...", "lado": "a favor|contra|neutro", "obs": ""}}]}}"""
    try:
        js, meta, modelo = gerar_json(prompt, cfg, busca=True, temperatura=0.3)
    except Exception as e:
        return {"ok": False, "motivo": f"pesquisa de fatos falhou: {e}", "fatos": [], "cortados": []}
    brutos = [f for f in (js.get("fatos") or []) if isinstance(f, dict)]
    # URLs da busca (redirecionamentos do Google) resolvidas: usadas quando o modelo erra a URL exata
    chunks = [c.get("web", {}) for c in (meta.get("groundingChunks") or [])]
    with ThreadPoolExecutor(8) as ex:
        reais = list(ex.map(lambda c: _resolver(c.get("uri", "")), chunks)) if chunks else []
    log(f"fatos: {len(brutos)} propostos por {modelo}; {len(reais)} páginas da busca; conferindo nas fontes")
    with ThreadPoolExecutor(8) as ex:
        res = list(ex.map(_verificar, brutos))
    # segunda chance: trocar a URL por uma página da busca do mesmo domínio
    for i, r in enumerate(res):
        if not r["ok"] and "não abriu" in r.get("motivo", ""):
            dom = urlparse(r.get("url", "")).netloc.lower().removeprefix("www.")
            for u in reais:
                if dom and dom in u and u != r.get("url"):
                    r2 = _verificar(dict(brutos[i], url=u))
                    if r2["ok"]:
                        res[i] = r2
                        break
    ok = [r for r in res if r["ok"]]
    for i, f in enumerate(ok, 1):
        f["id"] = i
    cortados = [{"afirmacao": r.get("afirmacao", ""), "url": r.get("url", ""), "motivo": r.get("motivo", "")} for r in res if not r["ok"]]
    dominios = {f["dominio"] for f in ok}
    minf = int(cfg["llm"].get("min_fontes", 3))
    log(f"fatos conferidos: {len(ok)} ok, {len(cortados)} cortados, {len(dominios)} fontes distintas")
    motivo = ""
    if len(dominios) < minf:
        motivo = f"só {len(dominios)} fonte(s) confirmada(s); mínimo {minf}"
    elif len(ok) < 5:
        motivo = f"só {len(ok)} fato(s) confirmado(s)"
    return {"ok": not motivo, "motivo": motivo, "tema": js.get("tema_pt") or tema, "angulo": js.get("angulo", ""), "financas": bool(js.get("financas")),
            "fatos": ok, "cortados": cortados, "modelo": modelo}
