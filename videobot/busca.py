"""Busca na web para a checagem de fatos, só por APIs oficiais:

- Tavily (TAVILY_API_KEY, plano grátis mensal): busca principal, inclusive de notícias recentes;
- Wikipedia (API pública, sem chave): última reserva, para contexto.

Devolve só URLs e títulos; quem baixa e confere as páginas é o facts.py.
"""
from __future__ import annotations

import requests

from .util import chave, log, nota

_avisados: set[str] = set()


def _avisar(prov: str, txt: str):
    if prov not in _avisados:
        _avisados.add(prov)
        nota(txt)


def tavily(q: str, n: int, dias: int | None) -> list[dict] | None:
    key = chave("TAVILY_API_KEY")
    if not key:
        return None
    body = {"query": q, "max_results": n, "search_depth": "basic", "include_answer": False}
    if dias:
        body["days"] = dias
        body["topic"] = "news"
    try:
        r = requests.post("https://api.tavily.com/search", json=body, timeout=40,
                          headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
    except requests.RequestException as e:
        log(f"  Tavily falhou ({str(e)[:80]})")
        return None
    if r.status_code != 200:
        _avisar("tavily", f"Busca: o Tavily respondeu HTTP {r.status_code} (chave inválida ou cota do mês esgotada); usei a reserva.")
        return None
    return [{"url": x.get("url", ""), "titulo": x.get("title", ""), "resumo": x.get("content", "")} for x in r.json().get("results", [])]


def wikipedia(q: str, n: int, dias: int | None) -> list[dict] | None:
    """API oficial da Wikipedia (sem chave). Serve de contexto quando as outras falham."""
    try:
        r = requests.get("https://en.wikipedia.org/w/api.php", timeout=20, headers={"User-Agent": "video-diario-ia/1.0"},
                         params={"action": "query", "list": "search", "srsearch": q, "srlimit": n, "format": "json"})
        res = r.json().get("query", {}).get("search", []) if r.status_code == 200 else []
    except Exception:
        return None
    return [{"url": "https://en.wikipedia.org/wiki/" + x["title"].replace(" ", "_"), "titulo": x["title"], "resumo": ""} for x in res]


FUNCOES = {"tavily": tavily, "wikipedia": wikipedia}


def buscar(q: str, cfg: dict, dias: int | None = None) -> list[dict]:
    bcfg = cfg.get("busca") or {}
    n = int(bcfg.get("resultados_por_busca", 6))
    for prov in bcfg.get("provedores") or ["tavily", "wikipedia"]:
        f = FUNCOES.get(prov)
        if not f:
            continue
        res = f(q, n, dias)
        if res:
            for x in res:
                x["via"] = prov
            return res
    return []
