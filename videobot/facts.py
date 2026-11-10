"""Etapa 3 (parte 1): fatos com fonte, conferidos baixando a página da fonte.

"Na dúvida, corte": se a página não abre ou o número não aparece nela, o fato sai.
"""
from __future__ import annotations

import html as H
import json
import re
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlparse

import requests

from .busca import buscar
from .llm import extrair_json, gerar, gerar_json
from .util import log, nota, sem_acento

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"
RUINS = ("medium.com", "blogspot.", "wordpress.com", "substack.com", "linkedin.com", "quora.com", "reddit.com", "youtube.com", "tiktok.com",
         "facebook.com", "x.com", "twitter.com", "instagram.com")
ESCALA = {"thousand": 1e3, "mil": 1e3, "k": 1e3, "million": 1e6, "milhão": 1e6, "milhões": 1e6, "mi": 1e6, "m": 1e6,
          "billion": 1e9, "bilhão": 1e9, "bilhões": 1e9, "bi": 1e9, "bn": 1e9, "b": 1e9,
          "trillion": 1e12, "trilhão": 1e12, "trilhões": 1e12, "tri": 1e12, "tn": 1e12, "t": 1e12}
EXTENSO = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10}


_CACHE: dict[str, str | None] = {}


def _texto(url: str) -> str | None:
    """Texto da página (baixado uma vez só por execução: a extração e a conferência usam o mesmo)."""
    if url not in _CACHE:
        _CACHE[url] = _baixar(url)
    return _CACHE[url]


def _baixar(url: str) -> str | None:
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
    if nums and not achou_trecho and not any(_numero_forte(n) for n in nums):
        # "1", "4", "6"... aparecem em qualquer página: sem a frase citada, não dá para dizer que o fato está lá
        return dict(f, ok=False, motivo="só números curtos (" + ", ".join(nums) + ") e a frase citada não está na página", dominio=dom)
    return dict(f, ok=True, conferidos=conferidos, dominio=dom)


def _numero_forte(n: str) -> bool:
    """Número específico o bastante para ser conferido sozinho: 3+ algarismos, decimal, % ou escala (bn, trillion...)."""
    t = n.strip().lower()
    if re.search(r"\d[.,]\d", t) or "%" in t:
        return True
    if re.search(r"\d\s*(thousand|million|billion|trillion|mil|milh|bilh|trilh|bn|tn|trn|k\b|m\b|b\b)", t):
        return True
    return len(re.sub(r"\D", "", t)) >= 3


CONFIAVEIS = ("reuters.com", "apnews.com", "afp.com", "cnbc.com", "bloomberg.com", "wsj.com", "ft.com", "theverge.com", "arstechnica.com",
              "spectrum.ieee.org", "nature.com", "science.org", "technologyreview.com", "wired.com", "techcrunch.com", "bbc.", "nytimes.com",
              "theguardian.com", "economist.com", "axios.com", "iea.org", "arxiv.org", ".gov", ".edu", "who.int", "oecd.org", "imf.org",
              "worldbank.org", "statista.com", "nvidia.com", "openai.com", "anthropic.com", "google", "microsoft.com", "meta.com",
              "apple.com", "amazon", "spacex.com", "nasa.gov", "g1.globo.com", "folha.uol.com.br", "estadao.com.br", "valor.globo.com",
              "tecmundo.com.br", "olhardigital.com.br", "canaltech.com.br", "wikipedia.org")


def _dominio(url: str) -> str:
    return urlparse(url).netloc.lower().removeprefix("www.")


def _confiavel(url: str) -> bool:
    d = _dominio(url)
    return any(c in d for c in CONFIAVEIS)


def _trechos(pg: str, limite: int) -> str:
    """Frases da página que têm números (é delas que saem os fatos), até `limite` caracteres."""
    frases = re.split(r"(?<=[.!?])\s+", pg)
    boas = [f.strip() for f in frases if re.search(r"\d", f) and 40 <= len(f.strip()) <= 400]
    out, total = [], 0
    for f in boas:
        if total + len(f) > limite:
            break
        out.append(f)
        total += len(f) + 1
    return " ".join(out)


def _plano(cand: dict, cfg: dict) -> tuple[dict, str]:
    tema = cand["tema"]
    ref = f'Título do vídeo de referência (só para entender o tema): "{cand.get("titulo")}"' if cand.get("titulo") else ""
    prompt = f"""Vamos pesquisar fatos com números para um vídeo brasileiro sobre {cfg['tema'].get('nicho', 'IA e tecnologia')}.
Tema: "{tema}". {ref}

Responda SOMENTE com JSON:
{{"tema_pt": "título curto do tema em PT-BR", "angulo": "ângulo do vídeo em 1 frase", "financas": true/false (se fala de dinheiro/investimento),
 "buscas": ["6 a 8 buscas para um buscador web, a maioria em inglês, específicas, cobrindo: números principais, quem defende, críticos e riscos, contexto histórico, dados oficiais"]}}"""
    try:
        js, _, modelo = gerar_json(prompt, cfg, temperatura=0.3, max_tokens=1200)
        if isinstance(js, dict) and js.get("buscas"):
            return js, modelo
    except Exception as e:
        nota(f"Fatos: não consegui gerar as buscas com IA ({str(e)[:120]}); usei o tema direto.")
    return {"tema_pt": tema, "angulo": "", "financas": False, "buscas": [tema] + ([cand["titulo"]] if cand.get("titulo") else [])}, ""


def _extrair(paginas: list[dict], tema: str, cfg: dict) -> tuple[list[dict], str]:
    blocos = "\n\n".join(f"### FONTE {i + 1}\nurl: {p['url']}\nveículo: {p['dominio']}\ntítulo: {p['titulo']}\ntexto: {p['trechos']}"
                         for i, p in enumerate(paginas))
    prompt = f"""Tema do vídeo: "{tema}".
Abaixo estão trechos REAIS de páginas da web. Extraia os fatos úteis para o vídeo, usando SOMENTE o que está escrito nos trechos.

Regras:
- Cada fato precisa de pelo menos um número que aparece literalmente no trecho.
- "numeros": os números exatamente como escritos no trecho (ex.: "2.1 trillion", "75 billion", "40%", "2028").
- "trecho": copie LITERALMENTE uma frase do texto da fonte que contém o número (até 25 palavras, no idioma original, sem mudar nada).
- "url": a url da FONTE de onde o trecho saiu, exatamente como está acima.
- "afirmacao": o fato reescrito em PT-BR, claro e fiel ao trecho.
- Ignore publicidade, menus, links e números soltos sem contexto. Se uma fonte não tiver nada útil, pule.
- No máximo 4 fatos por fonte e 12 no total: escolha os mais fortes. Seja breve em "obs".
- Use exatamente os nomes de campo abaixo, sem acento.

Responda SOMENTE com JSON:
{{"fatos": [{{"afirmacao": "...", "numeros": ["..."], "fonte": "nome do veículo", "url": "https://...", "data": "DD/MM/AAAA ou vazio", "trecho": "...", "lado": "a favor|contra|neutro", "obs": ""}}]}}

{blocos}"""
    try:
        txt, modelo = gerar(prompt, cfg, temperatura=0.2, max_tokens=6000)
    except Exception as e:
        log(f"  extração falhou neste lote ({str(e)[:400]})")
        return [], ""
    try:
        js = extrair_json(txt)
        fatos = js.get("fatos") if isinstance(js, dict) else js
    except Exception:
        fatos = _objetos_completos(txt)  # resposta cortada: aproveita os fatos que vieram inteiros
        log(f"  resposta cortada neste lote; aproveitei {len(fatos)} fato(s) completo(s)")
    urls = {p["url"] for p in paginas}
    dom = {p["url"]: p["dominio"] for p in paginas}
    out = []
    for f in fatos or []:
        f = _normalizar(f)
        if f and f["url"] in urls:
            f["fonte"] = f["fonte"] or dom[f["url"]]
            out.append(f)
    return out, modelo


def _normalizar(f) -> dict | None:
    """Padroniza os campos de um fato vindo da IA (aceita 'afirmação', números como texto etc.).
    Fato sem afirmação, sem url ou sem número/trecho é descartado."""
    if not isinstance(f, dict):
        return None
    g = {sem_acento(str(k)).lower().strip(): v for k, v in f.items()}
    afirm = str(g.get("afirmacao") or g.get("fato") or g.get("claim") or "").strip()
    url = str(g.get("url") or "").strip()
    nums = g.get("numeros") or g.get("numbers") or []
    if isinstance(nums, (str, int, float)):
        nums = [nums]
    nums = [str(n).strip() for n in nums if str(n).strip()]
    trecho = str(g.get("trecho") or g.get("quote") or "").strip()
    if not afirm or not url or not (nums or trecho):
        return None
    return {"afirmacao": afirm, "numeros": nums, "fonte": str(g.get("fonte") or "").strip(), "url": url,
            "data": str(g.get("data") or "").strip(), "trecho": trecho, "lado": str(g.get("lado") or "neutro").strip(),
            "obs": str(g.get("obs") or "").strip()}


def _objetos_completos(txt: str) -> list[dict]:
    """Objetos JSON inteiros dentro de um texto cortado no meio (ignora o último, incompleto)."""
    out, nivel, ini, em_str, esc = [], 0, -1, False, False
    i0 = txt.find("[")
    for i, ch in enumerate(txt[i0 + 1:] if i0 >= 0 else txt, start=(i0 + 1 if i0 >= 0 else 0)):
        if em_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                em_str = False
            continue
        if ch == '"':
            em_str, esc = True, False
        elif ch == "{":
            if nivel == 0:
                ini = i
            nivel += 1
        elif ch == "}" and nivel:
            nivel -= 1
            if nivel == 0:
                try:
                    out.append(json.loads(txt[ini:i + 1]))
                except json.JSONDecodeError:
                    pass
    return out


def _lotes(paginas: list[dict], max_chars: int) -> list[list[dict]]:
    lotes, atual, tam = [], [], 0
    for p in paginas:
        if atual and tam + len(p["trechos"]) > max_chars:
            lotes.append(atual)
            atual, tam = [], 0
        atual.append(p)
        tam += len(p["trechos"])
    if atual:
        lotes.append(atual)
    return lotes


def coletar(cand: dict, cfg: dict) -> dict:
    tema = cand["tema"]
    bcfg = cfg.get("busca") or {}
    plano, modelo = _plano(cand, cfg)
    buscas = [str(b) for b in plano.get("buscas", []) if str(b).strip()][:8]
    # 1. buscar: as primeiras buscas olham notícias recentes; as outras, a web toda
    dias = int(bcfg.get("dias_noticias", 90)) or None
    achados, vistos = [], set()
    for i, q in enumerate(buscas):
        for r in buscar(q, cfg, dias if i < 3 else None):
            u = r["url"].split("#")[0]
            d = _dominio(u)
            if u in vistos or not d or any(x in d for x in RUINS) or u.lower().endswith(".pdf"):
                continue
            vistos.add(u)
            achados.append(dict(r, url=u, dominio=d))
    if not achados:
        return {"ok": False, "motivo": "a busca na web não devolveu páginas (Tavily sem chave ou sem cota)",
                "fatos": [], "cortados": []}
    achados.sort(key=lambda r: not _confiavel(r["url"]))  # fontes conhecidas primeiro
    achados = achados[: int(bcfg.get("max_paginas", 18))]
    # 2. baixar as páginas
    with ThreadPoolExecutor(8) as ex:
        textos = list(ex.map(lambda r: _texto(r["url"]), achados))
    lim = int(bcfg.get("chars_por_pagina", 3500))
    paginas = []
    for r, t in zip(achados, textos):
        tr = _trechos(t, lim) if t else ""
        if len(tr) > 200:
            paginas.append(dict(r, trechos=tr))
    log(f"fatos: {len(buscas)} buscas, {len(achados)} páginas encontradas, {len(paginas)} abriram com números")
    # 3. extrair fatos em lotes pequenos (cabem nos limites dos planos grátis)
    brutos = []
    for lote in _lotes(paginas, int(bcfg.get("chars_por_lote", 11000))):
        fs, m = _extrair(lote, plano.get("tema_pt") or tema, cfg)
        brutos += fs
        modelo = m or modelo
    unicos, chaves = [], set()
    for f in brutos:
        k = (f.get("url"), tuple(sorted(str(n) for n in f.get("numeros") or [])))
        if k not in chaves:
            chaves.add(k)
            unicos.append(f)
    brutos = unicos[: int(bcfg.get("max_fatos", 30))]
    log(f"fatos: {len(brutos)} propostos por {modelo or 'nenhum modelo'}; conferindo nas fontes")
    # 4. conferir cada número na página (mesma regra de antes: na dúvida, corta)
    with ThreadPoolExecutor(8) as ex:
        res = list(ex.map(_verificar, brutos))
    ok = [r for r in res if r["ok"]]
    for i, f in enumerate(ok, 1):
        f["id"] = i
        f["fonte"] = f.get("fonte") or f.get("dominio", "")
    cortados = [{"afirmacao": r.get("afirmacao", ""), "url": r.get("url", ""), "motivo": r.get("motivo", "")} for r in res if not r["ok"]]
    dominios = {f["dominio"] for f in ok}
    minf = int(cfg["llm"].get("min_fontes", 3))
    log(f"fatos conferidos: {len(ok)} ok, {len(cortados)} cortados, {len(dominios)} fontes distintas")
    motivo = ""
    if len(dominios) < minf:
        motivo = f"só {len(dominios)} fonte(s) confirmada(s); mínimo {minf}"
    elif len(ok) < 5:
        motivo = f"só {len(ok)} fato(s) confirmado(s)"
    return {"ok": not motivo, "motivo": motivo, "tema": plano.get("tema_pt") or tema, "angulo": plano.get("angulo", ""),
            "financas": bool(plano.get("financas")), "fatos": ok, "cortados": cortados, "modelo": modelo}
