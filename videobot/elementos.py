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
    if nome == "__carregar_lista__":
        return None
    alvo = _norm(nome)
    achado = None
    for ic in _icones:
        nomes = [ic["title"]] + list(((ic.get("aliases") or {}).get("aka") or []))
        if any(_norm(n) == alvo for n in nomes):
            achado = ic
            break
    if not achado:
        return logo_commons(nome, pasta)  # marca fora do Simple Icons (ex.: Disney, Character.AI)
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
    return pessoa_commons(nome, pasta)  # sem foto na Wikipedia: busca na Commons pelo nome no arquivo


def _commons_busca(q: str, filtro: str, n: int = 12) -> list[dict]:
    js = _get("https://commons.wikimedia.org/w/api.php", params={
        "action": "query", "format": "json", "generator": "search", "gsrnamespace": 6, "gsrsearch": f"{q} {filtro}",
        "gsrlimit": n, "prop": "imageinfo", "iiprop": "url|size|mime|extmetadata", "iiurlwidth": 900,
        "iiextmetadatafilter": "LicenseShortName|License|Artist"}).json()
    out = []
    for pg in ((js.get("query") or {}).get("pages") or {}).values():
        ii = (pg.get("imageinfo") or [{}])[0]
        m = ii.get("extmetadata") or {}
        out.append({"titulo": pg.get("title", "").replace("File:", ""), "url": ii.get("url", ""), "thumb": ii.get("thumburl") or ii.get("url"),
                    "mime": ii.get("mime", ""), "w": ii.get("width") or 0, "h": ii.get("height") or 0,
                    "lic": (m.get("License") or {}).get("value") or (m.get("LicenseShortName") or {}).get("value", ""),
                    "licenca": (m.get("LicenseShortName") or {}).get("value", ""), "autor": (m.get("Artist") or {}).get("value", ""),
                    "pagina": ii.get("descriptionurl", "")})
    return out


def logo_commons(nome: str, pasta: Path) -> dict | None:
    """Logo na Wikimedia Commons: arquivo cujo nome tem a marca e 'logo' (logotipos na Commons são livres ou só texto)."""
    try:
        cands = _commons_busca(f'"{nome}" logo', "filetype:drawing|bitmap")
    except Exception:
        return None
    alvo = _norm_espacos(nome).split()
    for c in cands:
        t = _norm_espacos(c["titulo"])
        if "logo" in t and all(w in t.split() for w in alvo) and c.get("thumb"):
            try:
                from .midia import _baixar
                ext = ".png" if c["mime"] == "image/svg+xml" else (Path(c["thumb"].split("?")[0]).suffix or ".png")
                arq = _baixar(c["thumb"], pasta / f"logo_{re.sub(r'[^a-z0-9]', '_', nome.lower())[:30]}{ext}", 10)
            except Exception:
                continue
            return {"svg": arq.resolve().as_uri(), "cor": "#9aa3b2", "nome": nome, "fundo": "claro"}  # cores do arquivo: cartão claro
    return None


def pessoa_commons(nome: str, pasta: Path) -> dict | None:
    """Foto da pessoa na Commons: só arquivo cujo título tem o nome completo (primeiro e último nome) e licença livre.
    Sem reconhecimento facial: o nome no arquivo é a garantia de que é a pessoa."""
    from .midia import _baixar, _limpo, licenca_ok
    partes = _norm_espacos(nome).split()
    if len(partes) < 2:
        return None
    try:
        cands = _commons_busca(f'"{nome}"', "filetype:bitmap")
    except Exception:
        return None
    for c in cands:
        t = _norm_espacos(c["titulo"]).split()
        if partes[0] in t and partes[-1] in t and licenca_ok(c["lic"]) and min(c["w"], c["h"]) >= 400 \
                and re.search(r"\.jpe?g$", c["titulo"].lower()):
            try:
                arq = _baixar(c["thumb"], pasta / f"pessoa_{re.sub(r'[^a-z0-9]', '_', nome.lower())[:30]}.jpg", 20)
            except Exception:
                continue
            return {"src": arq.resolve().as_uri(), "credito": f"Foto: {_limpo(c['autor'], 50) or 'autor desconhecido'} / Wikimedia Commons ({c['licenca']})",
                    "pagina": c["pagina"], "nome": nome}
    return None


# ---------------------------------------------------------------- direção de arte (o que entra em cada cena)
def _prompt_arte(roteiro: dict) -> str:
    from .objetos3d import CATALOGO
    catalogo = "; ".join(f"{k} ({d})" for k, (d, _) in CATALOGO.items())
    cenas = "\n".join(f'- id "{sc["id"]}" ({sc.get("template", "")}): {sc["text"]}'
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
- "carimbo": opcional e RARO (no máximo 1 a cada 3 cenas), só um destes, e só quando a fala DAQUELA cena disser exatamente isso:
  "CONFIRMADO"/"DADO OFICIAL" (fato verificado, número oficial), "RECORDE" (a fala diz recorde/maior da história),
  "EM ALTA"/"EM QUEDA" (a fala diz que subiu/caiu), "ESTIMATIVA"/"PROJEÇÃO" (a fala fala de previsão, estimativa, expectativa),
  "ALERTA" (a fala fala de risco, perigo, cuidado), "MITO" (SÓ se a fala desmente uma crença: "é mito", "não é verdade", "falso").
  Na dúvida, "". Nunca sobre uma pessoa; proibido acusar ou rotular pessoas.
- "etiqueta": até 4 palavras, estilo "DOSSIÊ · CASO NVDA" / "LAB · FIBRA ÓPTICA".
- "destaque": a pessoa ou marca mais importante da cena (nome) ou "".
- "buscas": 2 buscas curtas EM INGLÊS (2 a 4 palavras) da foto/vídeo REAL que mostra o assunto concreto DESTA frase
  (1ª específica: pessoa/empresa/produto/lugar citado; 2ª um pouco mais ampla). [] se a frase for abstrata. "tipo": "video" se
  movimento ajuda (robôs, fábrica, trânsito, foguete), senão "foto".
- "objetos3d": 0 a 2 ids do CATÁLOGO 3D abaixo que mostram LITERALMENTE algo que a frase cita; [] na dúvida.
Varie: nem toda cena precisa de todos os campos; não repita a mesma pessoa/marca em todas as cenas, só onde a fala pede.

CATÁLOGO 3D: {catalogo}

CENAS:
{cenas}

Responda SOMENTE com JSON: {{"cenas": [{{"id": "...", "pessoas": [{{"nome": "...", "wiki": "...", "papel": "..."}}],
 "marcas": ["..."], "manchete": "...", "nota": {{"valor": "...", "rotulo": "..."}}, "carimbo": "", "etiqueta": "...", "destaque": "",
 "buscas": ["...", "..."], "tipo": "foto", "objetos3d": []}}]}}"""


def _texto_cena(sc: dict) -> str:
    """Fala + textos de tela da cena (sem os campos internos que começam com _)."""
    def junta(o):
        if isinstance(o, dict):
            return " ".join(junta(v) for k, v in o.items() if not str(k).startswith("_"))
        if isinstance(o, list):
            return " ".join(junta(v) for v in o)
        return o if isinstance(o, str) else ""
    return (sc.get("text", "") + " " + junta(sc.get("params") or {}))


def citado(nome: str, texto: str, apelidos: list[str] | None = None) -> bool:
    """O nome (ou um apelido) aparece como palavra(s) inteira(s) no texto? Ex.: 'OpenAI' em 'a OpenAI lançou'."""
    t = " " + _norm_espacos(texto) + " "
    for n in [nome] + list(apelidos or []):
        k = _norm_espacos(n)
        if len(k) >= 2 and f" {k} " in t:
            return True
        # nome principal da marca: "The Walt Disney Company" -> "disney" (sem palavras genéricas)
        miolo = [w for w in k.split() if w not in GENERICAS and len(w) >= 4]
        if miolo and f" {miolo[-1]} " in t:
            return True
    return False


GENERICAS = {"the", "company", "companies", "inc", "corp", "corporation", "group", "holdings", "technologies", "technology",
             "walt", "labs", "systems", "international", "global", "co", "ltd", "sa", "de", "do", "da"}


def pessoa_citada(nome: str, texto: str) -> bool:
    """Pessoa entra se o nome completo ou o sobrenome (palavra inteira) aparece no texto."""
    partes = _norm_espacos(nome).split()
    t = " " + _norm_espacos(texto) + " "
    return bool(partes) and (f" {' '.join(partes)} " in t or (len(partes[-1]) >= 3 and f" {partes[-1]} " in t))


def _apelidos(nome: str) -> list[str]:
    if not _icones:
        return []
    alvo = _norm(nome)
    for ic in _icones:
        nomes = [ic["title"]] + list(((ic.get("aliases") or {}).get("aka") or []))
        if any(_norm(n) == alvo for n in nomes):
            return nomes
    return []


APELIDOS_EXTRA = {"openai": ["ChatGPT", "GPT", "GPT-4", "GPT-5", "Sora"], "google": ["Gemini", "Google DeepMind", "DeepMind"],
                  "meta": ["Facebook", "Instagram", "WhatsApp", "Llama"], "anthropic": ["Claude"], "microsoft": ["Copilot", "Azure"]}


def marcas_no_texto(texto: str) -> list[str]:
    """Marcas do acervo escritas na fala com inicial maiúscula (ex.: 'Disney', 'Palantir'), fora do início de frase."""
    if not _icones:
        return []
    achadas = []
    for m in re.finditer(r"(?<![.!?]\s)(?<!^)\b([A-Z][\w&.+-]{2,}(?:\s[A-Z][\w&.+-]+)?)", texto):
        cand = m.group(1)
        for ic in _icones:
            if _norm(ic["title"]) == _norm(cand) and len(_norm(cand)) >= 3:
                achadas.append(ic["title"])
                break
    return list(dict.fromkeys(achadas))


ACUSATORIO = re.compile(r"espi|golp|fraud|mentir|culpad|crimin|ladr|corrupt|traid|pres[oa]\b|bandid|vigarist|farsant|"
                        r"escand|ilegal|trapac|enganad|acusad|suspeit|suposta|suposto", re.I)


def encurtar(texto: str, n: int) -> str:
    """Corta em até n caracteres sem partir palavra ("35 mil residências" nunca vira "35 mil residên")."""
    t = re.sub(r"\s+", " ", str(texto or "")).strip()
    if len(t) <= n:
        return t
    if " " not in t[:n + 1]:
        return t.split(" ")[0]  # palavra única longa: inteira (o quadro encolhe a fonte)
    return t[:n + 1].rsplit(" ", 1)[0].rstrip(" ,.;:-–—")


# carimbo só vale se a fala da cena disser aquilo (20/11: "MITO" em cima de fatos e "ALERTA" em cena neutra)
_CARIMBOS = {
    "CONFIRMADO": None, "DADO OFICIAL": None,  # precisam de fato verificado na cena (fact_ids)
    "RECORDE": r"recorde|maior (da|de toda a) hist|nunca antes|jamais|histori",
    "EM ALTA": r"\bsub(iu|iram|ir|indo|ida)|\balta\b|cresc|dispar|dobr|tripl|aument|salt(ou|o)\b|avan[cç]",
    "EM QUEDA": r"\bca(iu|íram|indo|ir)\b|queda|recu|despenc|encolh|diminu|perd(eu|a)\b|desaba",
    "ESTIMATIVA": r"estim|proje|previs|prev[eê]|expect|espera-se|esperad|pode chegar|deve (chegar|ser|valer)|calcul",
    "PROJEÇÃO": r"estim|proje|previs|prev[eê]|expect|espera-se|esperad|pode chegar|deve (chegar|ser|valer)|futur",
    "ALERTA": r"risco|perig|cuidado|alert|amea[cç]|aten[cç][aã]o|preocup|golpe|vulner",
    "MITO": r"\bmito|n[aã]o [eé] verdade|\bfals[oa]\b|lenda|engan(o|a)\b|ao contr[aá]rio do que|na verdade,? n[aã]o",
}
_SINONIMOS_CARIMBO = {"FATO": "CONFIRMADO", "VERDADE": "CONFIRMADO", "VERIFICADO": "CONFIRMADO", "OFICIAL": "DADO OFICIAL",
                      "FALSO": "MITO", "MENTIRA": "MITO", "PREVISÃO": "PROJEÇÃO", "PREVISAO": "PROJEÇÃO",
                      "PROJECAO": "PROJEÇÃO", "ATENÇÃO": "ALERTA", "ATENCAO": "ALERTA", "RISCO": "ALERTA", "ALTA": "EM ALTA",
                      "QUEDA": "EM QUEDA", "ESTIMADO": "ESTIMATIVA"}


def carimbo_coerente(carimbo: str, fala: str, tem_fato: bool) -> str:
    """Devolve o carimbo só se ele bate com a fala da cena; senão, nenhum (melhor sem carimbo que com carimbo errado)."""
    c = re.sub(r"\s+", " ", str(carimbo or "")).strip().upper()
    c = _SINONIMOS_CARIMBO.get(c, c)
    if c not in _CARIMBOS:
        return ""
    regra = _CARIMBOS[c]
    if regra is None:
        return c if tem_fato else ""
    return c if re.search(regra, fala or "", re.I) else ""


def carimbo_seguro(texto: str) -> str:
    """Carimbo nunca acusa ninguém (risco de difamação ao lado da foto de uma pessoa real)."""
    t = encurtar(texto, 24).upper()
    return "" if not t or ACUSATORIO.search(unicodedata.normalize("NFD", t).encode("ascii", "ignore").decode()) else t


def dirigir(roteiro: dict, cfg: dict) -> dict | None:
    """UMA chamada à IA decide, por cena: pessoas, marcas, manchete, número, carimbo, etiqueta, buscas de mídia e objetos 3D.
    Devolve {id_da_cena: {...}} ou None se falhar (aí cada etapa usa a própria chamada, como antes)."""
    from .llm import gerar_json
    cenas = [sc for ch in roteiro.get("chapters", []) for sc in ch.get("scenes", [])]
    try:
        arte, _, _ = gerar_json(_prompt_arte(roteiro), cfg, temperatura=0.4, max_tokens=5000)
    except Exception as e:
        nota(f"Direção de arte falhou ({str(e)[:90]}); cada etapa visual decide sozinha.")
        return None
    lst = [c for c in (arte.get("cenas") or []) if isinstance(c, dict)]
    por_id = {str(c.get("id")): c for c in lst}
    if not any(sc["id"] in por_id for sc in cenas) and len(lst) == len(cenas):
        por_id = {sc["id"]: c for sc, c in zip(cenas, lst)}  # o modelo devolveu "0", "1"...: casa pela ordem
    return por_id


def objetos_da_arte(roteiro: dict, arte: dict) -> int:
    """Objetos 3D escolhidos na direção de arte (só ids do catálogo e ligados à fala)."""
    from .objetos3d import CATALOGO, escolher
    n = 0
    for ch in roteiro.get("chapters", []):
        for sc in ch.get("scenes", []):
            a = arte.get(sc["id"])
            if a is None:
                continue
            ligados = escolher(sc, "")  # palavras da própria cena (rede de segurança contra objeto sem ligação)
            pedidos = [str(o).strip().lower() for o in (a.get("objetos3d") or []) if str(o).strip().lower() in CATALOGO]
            sc["objetos_revisados"] = [o for o in pedidos if o in ligados][:2]
            n += 1
    return n


def montar(roteiro: dict, cfg: dict, pasta: Path, arte: dict | None = None) -> list[dict]:
    """Preenche params._quadro de cada cena (recortes do dossiê). Devolve créditos das fotos de pessoas.

    Regras em código (não só na IA): marca e pessoa só entram se forem DITAS na cena (pessoa: também na fala anterior,
    por causa de "ele/ela"); a cena alterna quadro e 3D (ver alternar())."""
    if not (cfg.get("visual") or {}).get("quadro", True):
        return []
    cenas = [sc for ch in roteiro.get("chapters", []) for sc in ch.get("scenes", [])]
    por_id = arte if arte is not None else dirigir(roteiro, cfg)
    if por_id is None:
        nota("Quadro: sem direção de arte; cenas com o visual antigo.")
        return []
    dest = pasta / "quadro"
    logo("__carregar_lista__", dest)  # carrega o acervo (para apelidos e marcas escritas na fala)
    pessoas_cache, logos_cache, creditos, barrados = {}, {}, [], []
    anterior = ""
    cenas_desde_carimbo = 9
    for sc in cenas:
        a = por_id.get(sc["id"]) or {}
        texto = _texto_cena(sc)
        itens = []
        for p in (a.get("pessoas") or [])[:2]:
            if not isinstance(p, dict) or not p.get("nome"):
                continue
            if not pessoa_citada(p["nome"], texto + " " + anterior):
                barrados.append(p["nome"]); continue  # run 40: Bob Iger numa cena que só falava da Disney
            k = p["nome"].strip().lower()
            if k not in pessoas_cache:
                pessoas_cache[k] = foto_pessoa(p["nome"], str(p.get("wiki") or ""), dest)
                if pessoas_cache[k]:
                    creditos.append({"cena": sc["id"], "titulo": p["nome"], "credito": pessoas_cache[k]["credito"], "pagina": pessoas_cache[k]["pagina"]})
            f = pessoas_cache[k]
            if f:
                itens.append({"tipo": "pessoa", "src": f["src"], "nome": p["nome"], "papel": encurtar(p.get("papel"), 40), "credito": f["credito"]})
        propostas = [str(m.get("nome") if isinstance(m, dict) else m).strip() for m in (a.get("marcas") or [])]
        for nome in list(dict.fromkeys([n for n in propostas if n] + marcas_no_texto(sc.get("text", ""))))[:2]:
            apel = _apelidos(nome) + APELIDOS_EXTRA.get(_norm(nome), [])
            if not citado(nome, texto, apel):
                barrados.append(nome); continue  # runs 39/40: OpenAI e NVIDIA em cenas que não falavam delas
            k = nome.lower()
            if k not in logos_cache:
                logos_cache[k] = logo(nome, dest)
            if logos_cache[k] and not any(i.get("nome") == logos_cache[k]["nome"] for i in itens):
                itens.append({"tipo": "logo", **logos_cache[k]})
        prm = sc.setdefault("params", {})
        # foto/vídeo real da etapa de mídia vira recorte no quadro (não ocupa mais a tela inteira)
        if prm.get("_photo") or prm.get("_video"):
            itens.append({"tipo": "video" if prm.get("_video") else "foto", "src": prm.pop("_photo", ""), "video": prm.pop("_video", None),
                          "credito": prm.get("_credit", ""), "foco": prm.pop("_focus", "")})
        reais = len(itens)
        manchete = str(a.get("manchete") or "").strip()
        # a manchete não pode trazer marca que a cena não cita (20/11: "OpenAI vende ativos à Disney" numa cena sem OpenAI)
        if manchete and any(not citado(m, texto, _apelidos(m)) for m in marcas_no_texto(" " + manchete)):
            barrados.append(f"manchete '{manchete}'"); manchete = ""
        if manchete:
            itens.append({"tipo": "manchete", "texto": encurtar(manchete, 60)})
        nt = a.get("nota") if isinstance(a.get("nota"), dict) else {}
        if str(nt.get("valor") or "").strip():
            itens.append({"tipo": "nota", "valor": encurtar(nt["valor"], 22), "rotulo": encurtar(nt.get("rotulo"), 30)})
        destaque = str(a.get("destaque") or "").strip().lower()
        for it in itens:  # a pessoa/marca em destaque vai para o centro, maior
            if destaque and destaque in (it.get("nome") or "").lower():
                it["destaque"] = True
        carimbo = carimbo_coerente(carimbo_seguro(str(a.get("carimbo") or "")), sc.get("text", ""), bool(sc.get("fact_ids")))
        if carimbo and cenas_desde_carimbo < 2:  # raro: no máximo 1 a cada 3 cenas, para o carimbo ter peso
            carimbo = ""
        cenas_desde_carimbo = 0 if carimbo else cenas_desde_carimbo + 1
        if itens:
            prm["_quadro"] = {"itens": itens[:4], "carimbo": carimbo,
                              "etiqueta": encurtar(a.get("etiqueta") or roteiro.get("tema", ""), 40).upper(), "reais": reais}
        anterior = sc.get("text", "")
    # logos do Simple Icons (SVG de verdade) podem virar 3D extrudado
    logos_svg = {}
    for v in logos_cache.values():
        if v and str(v.get("svg", "")).endswith(".svg"):
            try:
                logos_svg[v["nome"]] = {"texto": Path(v["svg"].replace("file:///", "")).read_text(encoding="utf-8"), "cor": v["cor"]}
            except Exception:
                pass
    alternar(cenas, logos_svg)
    preparar_3d(cenas, logos_svg)
    n = sum(1 for sc in cenas if (sc.get("params") or {}).get("_quadro"))
    n3d = sum(1 for sc in cenas if sc.get("objetos_revisados") and not (sc.get("params") or {}).get("_quadro"))
    log(f"quadro: {n}/{len(cenas)} cenas com recortes, {n3d} com objeto 3D ({len([v for v in pessoas_cache.values() if v])} pessoa(s), "
        f"{len([v for v in logos_cache.values() if v])} logo(s)" + (f"; fora por não serem citados na cena: {', '.join(dict.fromkeys(barrados))}" if barrados else "") + ")")
    return creditos


def _numero_da_cena(prm: dict) -> str:
    """O número que a cena mostra na tela (ex.: 'US$ 5 TRI', '17%'), para virar texto 3D."""
    def fmt(o):
        try:
            v = float(o.get("value"))
        except (TypeError, ValueError):
            return ""
        dec = int(o.get("decimals") or (0 if v == int(v) else 1))
        n = f"{v:,.{dec}f}".replace(",", "X").replace(".", ",").replace("X", ".")
        return f"{o.get('prefix') or ''}{n}{o.get('suffix') or ''}".strip().upper()
    for o in (prm, prm.get("left") or {}, *(prm.get("items") or [])[:1]):
        if isinstance(o, dict) and o.get("value") is not None:
            t = fmt(o)
            if t and len(t) <= 11:
                return t
    if prm.get("value") is not None and "label" in prm:  # gauge
        return f"{prm['value']}%"
    return ""


def _palavra_da_cena(prm: dict) -> str:
    hl = prm.get("highlight") or []
    if isinstance(hl, list) and hl:
        p = str(hl[0]).strip().upper()
        if 2 <= len(p) <= 11:
            return p
    return ""


def preparar_3d(cenas: list[dict], logos_svg: dict[str, dict]) -> None:
    """3D feito em código e ligado à cena, para as cenas sem quadro (nenhum modelo pronto):
    objeto do catálogo citado na fala > logo da marca citada (extrudada do SVG) > número da cena > palavra de destaque."""
    from .texto3d import svg_de_texto
    for sc in cenas:
        prm = sc.setdefault("params", {})
        if prm.get("_quadro") or sc.get("objetos_revisados"):
            continue
        texto = _texto_cena(sc)
        extra = None
        for nome, lg in logos_svg.items():
            if citado(nome, texto, _apelidos(nome) + APELIDOS_EXTRA.get(_norm(nome), [])):
                extra = {"svg": lg["texto"], "cor": lg["cor"]}
                break
        if not extra:
            alvo = _numero_da_cena(prm) or _palavra_da_cena(prm)
            svg = svg_de_texto(alvo) if alvo else None
            if svg:
                extra = {"svg": svg, "texto": True}
        if extra:
            sc["objetos_extra"] = [extra]


def alternar(cenas: list[dict], logos_svg: dict[str, dict] | None = None) -> None:
    """Alterna o visual entre as cenas:
    - cena com foto/vídeo/pessoa -> quadro de dossiê;
    - cena cujo único recorte real é a logo -> alterna entre o cartão no quadro e a logo extrudada em 3D;
    - cena só com peças 2D (manchete/post-it) e com objeto 3D ligado à fala -> 3D, a cada duas cenas assim
      (e sempre que já houver dois quadros seguidos), para o vídeo não ficar só de recortes;
    - cena sem nada -> 3D (objeto, logo, número ou palavra da cena)."""
    seguidos, so2d, so_logo = 0, 0, 0
    for sc in cenas:
        prm = sc.setdefault("params", {})
        q = prm.get("_quadro")
        tem3d = bool(sc.get("objetos_revisados"))
        reais = [i for i in (q or {}).get("itens", []) if i["tipo"] in ("foto", "video", "pessoa", "logo")]
        so_logos = bool(reais) and all(i["tipo"] == "logo" for i in reais) and \
            any(i.get("nome") in (logos_svg or {}) for i in reais)
        if q and so_logos:
            so_logo += 1
            if so_logo % 2 == 0 or seguidos >= 2:
                del prm["_quadro"]  # esta vira logo em 3D
                seguidos = 0
                continue
        pessoa = any(i["tipo"] == "pessoa" for i in (q or {}).get("itens", []))
        pode3d = tem3d or bool(_numero_da_cena(prm) or _palavra_da_cena(prm))
        if q and seguidos >= 2 and pode3d and not pessoa:
            del prm["_quadro"]  # 3 quadros seguidos cansam: esta vira 3D (objeto, número ou palavra da cena)
            seguidos = 0
            continue
        if q and q.get("reais"):
            seguidos += 1
            continue
        if q and tem3d:
            so2d += 1
            if seguidos >= 2 or so2d % 2 == 0:
                del prm["_quadro"]  # esta vira cena 3D
                seguidos = 0
                continue
        if q:
            seguidos += 1
        else:
            seguidos = 0
