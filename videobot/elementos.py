"""Direção de arte por cena: o "quadro de dossiê" (pessoas, marcas, fotos/vídeos e ilustração 2D desenhada em código).

Para cada cena, a IA decide o que aparece no quadro, SEMPRE ligado à fala dela:
- pessoa citada  -> foto da página dela na Wikipedia (arquivo da Wikimedia Commons com licença livre);
- marca citada   -> logo oficial do acervo Simple Icons (CC0), na cor da marca;
- peças de dossiê-> recorte de jornal com a manchete da cena, post-it com o número, carimbo, etiqueta (texto do roteiro);
- foto/vídeo real-> o que a etapa de mídia escolheu (videobot/midia.py) entra como polaroide, não em tela cheia.
O motor (engine/quadro.js) monta tudo como recortes presos num quadro, com alfinete, carimbo e legenda.
"""
from __future__ import annotations

import re
import unicodedata
import urllib.parse
from pathlib import Path

import requests

from .util import log, nota

UA = "video-diario-ia/1.0 (https://github.com/8saulo/video-diario-ia)"
SIMPLE_ICONS = "https://cdn.jsdelivr.net/npm/simple-icons@15.0.0/"
_icones: list[dict] = []


def _get(url, **kw):
    r = requests.get(url, headers={"User-Agent": UA}, timeout=kw.pop("timeout", 20), **kw)
    r.raise_for_status()
    return r


# ---------------------------------------------------------------- marcas (Simple Icons, CC0)
def slug_simple_icons(titulo: str) -> str:
    """Mesma regra do titleToSlug do Simple Icons."""
    s = titulo.lower().replace("+", "plus").replace(".", "dot").replace("&", "and")
    for a, b in (("đ", "d"), ("ħ", "h"), ("ı", "i"), ("ĸ", "k"), ("ŀ", "l"), ("ł", "l"), ("ß", "ss"), ("ŧ", "t")):
        s = s.replace(a, b)
    s = unicodedata.normalize("NFD", s)
    return re.sub(r"[^a-z0-9]", "", s)


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", unicodedata.normalize("NFD", (s or "").lower()))


def logo(nome: str, pasta: Path) -> dict | None:
    """Logo da marca: {svg (arquivo), cor, nome} ou None se o acervo não tiver."""
    global _icones
    if not _icones:
        try:
            _icones.extend(_get(SIMPLE_ICONS + "data/simple-icons.json", timeout=30).json())
        except Exception as e:
            log(f"  quadro: não consegui baixar a lista de logos ({str(e)[:80]})")
            return None
    alvo = _norm(nome)
    achado = None
    for ic in _icones:
        nomes = [ic["title"]] + list(((ic.get("aliases") or {}).get("aka") or []))
        if any(_norm(n) == alvo for n in nomes):
            achado = ic
            break
    if not achado:
        return None
    slug = achado.get("slug") or slug_simple_icons(achado["title"])
    try:
        svg = _get(SIMPLE_ICONS + f"icons/{slug}.svg").text
    except Exception:
        return None
    if "<svg" not in svg:
        return None
    pasta.mkdir(parents=True, exist_ok=True)
    arq = pasta / f"logo_{slug}.svg"
    arq.write_text(svg.replace("<svg ", f'<svg fill="#{achado["hex"]}" ', 1), encoding="utf-8")
    return {"svg": arq.resolve().as_uri(), "cor": "#" + achado["hex"], "nome": achado["title"]}


# ---------------------------------------------------------------- pessoas (Wikipedia + licença da Commons)
def _licenca_commons(arquivo: str) -> dict | None:
    js = _get("https://commons.wikimedia.org/w/api.php", params={
        "action": "query", "format": "json", "titles": "File:" + arquivo, "prop": "imageinfo",
        "iiprop": "extmetadata|url", "iiurlwidth": 900,
        "iiextmetadatafilter": "LicenseShortName|License|Artist"}).json()
    for p in (js.get("query") or {}).get("pages", {}).values():
        ii = (p.get("imageinfo") or [{}])[0]
        m = ii.get("extmetadata") or {}
        from .midia import _limpo, licenca_ok
        lic = (m.get("License") or {}).get("value") or (m.get("LicenseShortName") or {}).get("value", "")
        if not licenca_ok(lic):
            return None
        return {"url": ii.get("thumburl") or ii.get("url"), "autor": _limpo((m.get("Artist") or {}).get("value", ""), 50) or "autor desconhecido",
                "licenca": (m.get("LicenseShortName") or {}).get("value", lic), "pagina": ii.get("descriptionurl", "")}
    return None


def _mesma_pessoa(nome: str, titulo: str) -> bool:
    """O título da página tem que ser a pessoa: primeiro e último nome presentes e nada de 'scandal', 'case'..."""
    t = _norm_espacos(titulo)
    partes = _norm_espacos(nome).split()
    if not partes or re.search(r"scandal|case|affair|controversy|caso|escandalo|list of|family|award", t):
        return False
    return partes[0] in t.split() and partes[-1] in t.split()


def _norm_espacos(s: str) -> str:
    s = unicodedata.normalize("NFD", (s or "").lower())
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]", " ", s)).strip()


def foto_pessoa(nome: str, wiki: str, pasta: Path) -> dict | None:
    """Foto principal da página da pessoa na Wikipedia (en, depois pt), só se o arquivo tiver licença livre."""
    for lang, titulo in (("en", wiki or nome), ("pt", nome)):
        try:
            d = _get(f"https://{lang}.wikipedia.org/api/rest_v1/page/summary/" + urllib.parse.quote(titulo.replace(" ", "_"))).json()
        except Exception:
            continue
        if d.get("type") == "disambiguation" or not _mesma_pessoa(nome, d.get("title", "")):
            continue  # redirecionamento para outra página (ex.: "Kimberly Powell" -> "Jensen Huang spying scandal")
        src = (d.get("originalimage") or d.get("thumbnail") or {}).get("source", "")
        if "upload.wikimedia.org" not in src:
            continue
        arquivo = urllib.parse.unquote(src.split("?")[0].rsplit("/", 1)[-1])
        if "/thumb/" in src:
            arquivo = urllib.parse.unquote(src.split("/thumb/")[1].split("/")[2])
        try:
            lic = _licenca_commons(arquivo)
        except Exception:
            lic = None
        if not lic or not lic.get("url"):
            continue
        try:
            from .midia import _baixar
            ext = Path(lic["url"].split("?")[0]).suffix.lower() or ".jpg"
            arq = _baixar(lic["url"], pasta / f"pessoa_{re.sub(r'[^a-z0-9]', '_', nome.lower())[:30]}{ext}", 20)
        except Exception:
            continue
        return {"src": arq.resolve().as_uri(), "credito": f"Foto: {lic['autor']} / Wikimedia Commons ({lic['licenca']})",
                "pagina": lic["pagina"], "nome": d.get("title") or nome}
    return None


# ---------------------------------------------------------------- direção de arte (o que entra em cada cena)
def _prompt_arte(roteiro: dict) -> str:
    cenas = "\n".join(f'- [{sc["id"]}] ({sc.get("template", "")}) {sc["text"]}'
                      for ch in roteiro.get("chapters", []) for sc in ch.get("scenes", []))
    return f"""Você é diretor de arte de vídeos curtos no estilo "dossiê / quadro de investigação": fotos recortadas presas num
quadro, logos, crachás, recortes de jornal, post-its e carimbos. Tema do vídeo: "{roteiro.get('tema', '')}".
Para CADA cena, decida o que aparece no quadro, sempre ligado ao que a fala DAQUELA cena diz:
- "pessoas": figuras públicas REAIS citadas na fala (ou a quem ela se refere, ex.: "ele"); "nome" completo, "wiki" = título exato
  da página na Wikipedia em inglês, "papel" curto (ex.: "CEO · NVIDIA"). Nunca invente; pessoa comum/genérica não entra.
- "marcas": empresas, produtos ou órgãos REAIS citados (nome oficial: "NVIDIA", "OpenAI", "Huawei", "Netflix").
- "manchete": 3 a 7 palavras em PT-BR, como manchete de jornal recortada, resumindo a revelação da cena (sem copiar a fala).
- "nota": opcional, {{"valor": "número da fala com algarismos e unidade (ex.: '10 Gbps', '-40%')", "rotulo": "até 4 palavras"}}
  para um post-it; só se a fala tiver número.
- "carimbo": opcional, até 2 palavras (ex.: "CONFIRMADO", "MITO", "SUPOSTA ESPIÃ", "PERIGO").
- "etiqueta": até 4 palavras, estilo "DOSSIÊ · CASO NVDA" / "LAB · FIBRA ÓPTICA".
- "destaque": a pessoa ou marca mais importante da cena (nome) ou "".
Varie: nem toda cena precisa de todos os campos; não repita a mesma pessoa/marca em todas as cenas, só onde a fala pede.

CENAS:
{cenas}

Responda SOMENTE com JSON: {{"cenas": [{{"id": "...", "pessoas": [{{"nome": "...", "wiki": "...", "papel": "..."}}],
 "marcas": ["..."], "manchete": "...", "nota": {{"valor": "...", "rotulo": "..."}}, "carimbo": "", "etiqueta": "...", "destaque": ""}}]}}"""


def montar(roteiro: dict, cfg: dict, pasta: Path) -> list[dict]:
    """Preenche params._quadro de cada cena (recortes do dossiê). Devolve créditos das fotos de pessoas."""
    from .llm import gerar_json
    if not (cfg.get("visual") or {}).get("quadro", True):
        return []
    cenas = [sc for ch in roteiro.get("chapters", []) for sc in ch.get("scenes", [])]
    try:
        arte, _, _ = gerar_json(_prompt_arte(roteiro), cfg, temperatura=0.4, max_tokens=4000)
    except Exception as e:
        nota(f"Quadro: a direção de arte falhou ({str(e)[:90]}); cenas com o visual antigo.")
        return []
    por_id = {str(c.get("id")): c for c in (arte.get("cenas") or []) if isinstance(c, dict)}
    dest = pasta / "quadro"
    pessoas_cache, logos_cache, creditos = {}, {}, []
    for sc in cenas:
        a = por_id.get(sc["id"]) or {}
        itens = []
        for p in (a.get("pessoas") or [])[:2]:
            if not isinstance(p, dict) or not p.get("nome"):
                continue
            k = p["nome"].strip().lower()
            if k not in pessoas_cache:
                pessoas_cache[k] = foto_pessoa(p["nome"], str(p.get("wiki") or ""), dest)
                if pessoas_cache[k]:
                    creditos.append({"cena": sc["id"], "titulo": p["nome"], "credito": pessoas_cache[k]["credito"], "pagina": pessoas_cache[k]["pagina"]})
            f = pessoas_cache[k]
            if f:
                itens.append({"tipo": "pessoa", "src": f["src"], "nome": p["nome"], "papel": str(p.get("papel") or "")[:40], "credito": f["credito"]})
        for m in (a.get("marcas") or [])[:2]:
            nome = str(m.get("nome") if isinstance(m, dict) else m).strip()
            if not nome:
                continue
            k = nome.lower()
            if k not in logos_cache:
                logos_cache[k] = logo(nome, dest)
            if logos_cache[k]:
                itens.append({"tipo": "logo", **logos_cache[k]})
        prm = sc.setdefault("params", {})
        # foto/vídeo real da etapa de mídia vira recorte no quadro (não ocupa mais a tela inteira)
        if prm.get("_photo") or prm.get("_video"):
            itens.append({"tipo": "video" if prm.get("_video") else "foto", "src": prm.pop("_photo", ""), "video": prm.pop("_video", None),
                          "credito": prm.get("_credit", ""), "foco": prm.pop("_focus", "")})
        manchete = str(a.get("manchete") or "").strip()
        if manchete:
            itens.append({"tipo": "manchete", "texto": manchete[:60]})
        nt = a.get("nota") if isinstance(a.get("nota"), dict) else {}
        if str(nt.get("valor") or "").strip():
            itens.append({"tipo": "nota", "valor": str(nt["valor"])[:14], "rotulo": str(nt.get("rotulo") or "")[:30]})
        destaque = str(a.get("destaque") or "").strip().lower()
        for it in itens:  # a pessoa/marca em destaque vai para o centro, maior
            if destaque and destaque in (it.get("nome") or "").lower():
                it["destaque"] = True
        prm["_quadro"] = {"itens": itens[:4], "carimbo": str(a.get("carimbo") or "")[:24].upper(),
                          "etiqueta": str(a.get("etiqueta") or roteiro.get("tema", ""))[:40].upper()}
        if not itens:
            del prm["_quadro"]  # sem nada: a cena fica com o 3D (fallback)
    n = sum(1 for sc in cenas if (sc.get("params") or {}).get("_quadro"))
    log(f"quadro: {n}/{len(cenas)} cenas com recortes ({len([v for v in pessoas_cache.values() if v])} pessoa(s), "
        f"{len([v for v in logos_cache.values() if v])} logo(s))")
    return creditos
