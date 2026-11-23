"""Etapas 1 e 2: referências no YouTube dos últimos N dias, CRIVO 1, notas a–e e vencedor.

Caminho principal: YouTube Data API v3 (secret YOUTUBE_API_KEY).
Alternativa: leitura das páginas públicas (busca com sp=CAMSAggE + página /watch).
Se as duas falharem: tema da lista de reserva (respeitando o veto de 7 dias).
A cada dia é sorteada uma categoria de TI (config tema.categorias): buscas, triagem e reserva seguem a categoria.
"""
from __future__ import annotations

import datetime as dt
import json
import math
import random
import re
from concurrent.futures import ThreadPoolExecutor

import requests

from .llm import gerar_json
from .util import chave, log, nota, tokens

UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"
YT = "https://www.googleapis.com/youtube/v3"


# ---------------------------------------------------------------- YouTube Data API
def _api(path, params, key):
    """key = chave de API ou "Bearer <token>" (OAuth do canal, escopo youtube.readonly)."""
    cab = {"Authorization": key} if str(key).startswith("Bearer ") else {"X-Goog-Api-Key": key}
    r = requests.get(f"{YT}/{path}", params=params, headers=cab, timeout=30)
    r.raise_for_status()
    return r.json()


def _iso_dur(s: str) -> int:
    m = re.match(r"P(?:(\d+)D)?T?(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", s or "")
    if not m:
        return 0
    d, h, mi, se = (int(x or 0) for x in m.groups())
    return d * 86400 + h * 3600 + mi * 60 + se


def via_api(buscas, janela, por_busca, key) -> list[dict]:
    depois = (dt.datetime.utcnow() - dt.timedelta(days=janela)).strftime("%Y-%m-%dT%H:%M:%SZ")
    ids = []
    for q in buscas:
        js = _api("search", {"part": "snippet", "q": q, "type": "video", "order": "viewCount", "publishedAfter": depois,
                             "maxResults": min(50, por_busca), "relevanceLanguage": "en"}, key)
        for it in js.get("items", []):
            v = it["id"].get("videoId")
            if v and v not in ids:
                ids.append(v)
    out = []
    for i in range(0, len(ids), 50):
        js = _api("videos", {"part": "snippet,statistics,contentDetails", "id": ",".join(ids[i:i + 50])}, key)
        out += js.get("items", [])
    canais = list({v["snippet"]["channelId"] for v in out})
    subs = {}
    for i in range(0, len(canais), 50):
        js = _api("channels", {"part": "statistics", "id": ",".join(canais[i:i + 50])}, key)
        for c in js.get("items", []):
            st = c.get("statistics", {})
            subs[c["id"]] = None if st.get("hiddenSubscriberCount") else int(st.get("subscriberCount", 0))
    res = []
    for v in out:
        sn, st = v["snippet"], v.get("statistics", {})
        res.append({"id": v["id"], "url": f"https://www.youtube.com/watch?v={v['id']}", "titulo": sn["title"], "canal": sn["channelTitle"],
                    "inscritos": subs.get(sn["channelId"]), "views": int(st.get("viewCount", 0)),
                    "likes": int(st["likeCount"]) if "likeCount" in st else None,
                    "comentarios": int(st["commentCount"]) if "commentCount" in st else None,
                    "duracao_s": _iso_dur(v["contentDetails"].get("duration")), "publicado": sn["publishedAt"][:10],
                    "descricao": (sn.get("description") or "")[:200], "idioma": sn.get("defaultAudioLanguage") or sn.get("defaultLanguage") or ""})
    return res


# ---------------------------------------------------------------- páginas públicas
S = requests.Session()
S.headers.update({"User-Agent": UA, "Accept-Language": "en-US,en;q=0.9"})
S.cookies.set("CONSENT", "YES+cb", domain=".youtube.com")
S.cookies.set("SOCS", "CAI", domain=".youtube.com")


def _json_var(html: str, nome: str):
    m = re.search(nome + r"\s*=\s*(\{.+?\});\s*(?:var |</script>)", html, re.S)
    return json.loads(m.group(1)) if m else None


def _num(txt: str | None) -> int | None:
    if not txt:
        return None
    t = txt.replace(",", "").strip()
    m = re.match(r"([\d.]+)\s*([KMB])?", t, re.I)
    if not m:
        return None
    v = float(m.group(1))
    return int(v * {"K": 1e3, "M": 1e6, "B": 1e9}.get((m.group(2) or "").upper(), 1))


def _achar(o, chave_):
    if isinstance(o, dict):
        for k, v in o.items():
            if k == chave_:
                yield v
            else:
                yield from _achar(v, chave_)
    elif isinstance(o, list):
        for v in o:
            yield from _achar(v, chave_)


def _busca_publica(q):
    r = S.get("https://www.youtube.com/results", params={"search_query": q, "sp": "CAMSAggE"}, timeout=30)
    data = _json_var(r.text, r"var ytInitialData")
    out = []
    for vr in _achar(data or {}, "videoRenderer"):
        vid = vr.get("videoId")
        views = _num(re.sub(r"[^\d,.KMB]", "", (vr.get("viewCountText", {}) or {}).get("simpleText", "")))
        if vid:
            out.append((vid, views or 0))
    return out


def _watch(vid):
    try:
        h = S.get(f"https://www.youtube.com/watch?v={vid}", timeout=30).text
        pr = _json_var(h, r"var ytInitialPlayerResponse")
        if not pr:
            return None
        vd = pr.get("videoDetails", {})
        mf = pr.get("microformat", {}).get("playerMicroformatRenderer", {})
        meta = re.search(r'<meta name="title" content="([^"]*)"', h)
        likes = re.search(r"along with ([\d,]+) other people", h)
        subs = re.search(r'"subscriberCountText":\{"accessibility":\{"accessibilityData":\{"label":"([\d.,]+[KMB]?) subscribers', h)
        com = re.search(r'"commentCount":\{"simpleText":"([\d.,KMB]+)"', h) or re.search(r'"contextualInfo":\{"runs":\[\{"text":"([\d.,KMB]+)"', h)
        import html as H
        return {"id": vid, "url": f"https://www.youtube.com/watch?v={vid}", "titulo": H.unescape(meta.group(1)) if meta else vd.get("title", ""),
                "canal": vd.get("author", ""), "inscritos": _num(subs.group(1)) if subs else None, "views": int(vd.get("viewCount", 0) or 0),
                "likes": int(likes.group(1).replace(",", "")) if likes else None, "comentarios": _num(com.group(1)) if com else None,
                "duracao_s": int(vd.get("lengthSeconds", 0) or 0), "publicado": (mf.get("publishDate") or "")[:10],
                "descricao": (vd.get("shortDescription") or "")[:200], "idioma": ""}
    except Exception:
        return None


def via_paginas(buscas, por_busca) -> list[dict]:
    vistos = {}
    with ThreadPoolExecutor(6) as ex:
        for res in ex.map(_busca_publica, buscas):
            for vid, views in res[:por_busca]:
                vistos[vid] = max(views, vistos.get(vid, 0))
    top = sorted(vistos, key=vistos.get, reverse=True)[:60]
    with ThreadPoolExecutor(8) as ex:
        return [w for w in ex.map(_watch, top) if w]


# ---------------------------------------------------------------- notas
def _clip(x):
    return max(0.0, min(10.0, x))


def notas_metricas(c):
    v = c["views"] or 0
    c["nota_a"] = round(_clip(10 * math.log10(max(v, 1) / 1e4) / 3), 1)  # 10 mil → 0, 10 mi → 10
    lr = (c["likes"] / v) if (c["likes"] is not None and v) else None
    cr = (c["comentarios"] / v) if (c["comentarios"] is not None and v) else None
    c["curt_views"], c["coment_views"] = lr, cr
    c["nota_b"] = round(_clip((lr / 0.04 * 5 if lr is not None else 2.5) + (cr / 0.005 * 5 if cr is not None else 2.5)), 1)
    s = c.get("inscritos")
    vps = (v / s) if s else None
    c["views_insc"] = vps
    aut = min(3.0, max(0.0, math.log10(s / 1e3))) if s else 1.0  # 1 mil → 0, 1 mi → 3
    alg = 7 * min(1.0, math.log10(1 + (vps or 1)) / math.log10(51))
    c["nota_c"] = round(_clip(aut + alg), 1)


# ---------------------------------------------------------------- orquestração
_VAZIAS = set("""para como sobre pode podem mais menos quanto quanta realmente isso essa esse esta este porque entre depois antes
contra segundo vale tanto verdade funciona funcionam ja que dos das nos nas uma uns umas sera sao tem estao vai vao seu sua
seus suas ainda agora hoje novo nova novos novas what does really how much""".split())
# o mesmo assunto dito com outras palavras ("energia" x "consumo energético" x "conta de luz")
_SINONIMOS = {"consu": "energ", "eletr": "energ", "gasta": "energ", "gasto": "energ", "watts": "energ", "luz": "energ",
              "traba": "empre", "vagas": "empre", "profi": "empre", "carre": "empre", "robos": "robo", "human": "robo"}


def _raizes(tema: str) -> set:
    """Raízes de 5 letras das palavras que dizem o assunto (energia/energético → energ), com sinônimos juntados."""
    out = set()
    for t in tokens(tema):
        if t in _VAZIAS or (len(t) <= 3 and t != "luz"):
            continue
        r = t[:5]
        out.add(_SINONIMOS.get(r, r))
    return out


def _parecidos(a: str, b: str) -> bool:
    ra, rb = _raizes(a), _raizes(b)
    return bool(ra and rb and len(ra & rb) / min(len(ra), len(rb)) >= 0.5)


def _repetido(tema: str, hist: list, hoje: dt.date, dias: int) -> bool:
    """Tema já usado nos últimos `dias`: compara com o tema do roteiro e com o tema que saiu da pesquisa/reserva."""
    for h in hist:
        try:
            d = dt.date.fromisoformat(h["data"])
        except Exception:
            continue
        if (hoje - d).days <= dias and any(_parecidos(tema, h.get(k) or "") for k in ("tema", "tema_pesquisa")):
            return True
    return False


def _ultimo_uso(tema: str, hist: list) -> str:
    """Data do último vídeo com assunto parecido ('' = nunca usado)."""
    datas = [h.get("data", "") for h in hist if any(_parecidos(tema, h.get(k) or "") for k in ("tema", "tema_pesquisa"))]
    return max(datas) if datas else ""


def _tem_termo(texto: str, termos) -> bool:
    """O texto cita algum dos termos? Palavra inteira (aceita 1 letra de gênero/plural no fim); termo com espaço = expressão."""
    tk = tokens(texto)
    junto = " " + " ".join(tk) + " "
    for w in termos or []:
        w = " ".join(tokens(str(w)))
        if not w:
            continue
        if " " in w:
            if f" {w} " in junto:
                return True
        elif any(t == w or (len(w) >= 5 and len(t) in (len(w), len(w) + 1) and t[:len(w) - 1] == w[:-1]) for t in tk):
            return True
    return False


def categoria_de(tema: str, cats: dict) -> str:
    """Categoria de um tema pelas palavras de cada uma (a de mais acertos; '' se nenhuma bate)."""
    melhor, n = "", 0
    for nome, c in (cats or {}).items():
        k = sum(_tem_termo(tema, [w]) for w in (c or {}).get("palavras") or [])
        if k > n:
            melhor, n = nome, k
    return melhor


def _cansado(tema: str, tcfg: dict, hist: list, hoje: dt.date) -> bool:
    """Assunto saturado no canal (ex.: energia/data center): vetado por `assuntos_cansados.dias` se já saiu nesse período."""
    ac = tcfg.get("assuntos_cansados") or {}
    termos = ac.get("termos") or []
    if not termos or not _tem_termo(tema, termos):
        return False
    dias = int(ac.get("dias", 30))
    for h in hist:
        try:
            d = dt.date.fromisoformat(h["data"])
        except Exception:
            continue
        if (hoje - d).days <= dias and any(_tem_termo(h.get(k) or "", termos) for k in ("tema", "tema_pesquisa")):
            return True
    return False


def vetado(tema: str, tcfg: dict, hist: list, hoje: dt.date) -> bool:
    return _repetido(tema, hist, hoje, int(tcfg.get("nao_repetir_dias", 7))) or _cansado(tema, tcfg, hist, hoje)


def escolher_categoria(cfg: dict, hist: list, hoje: dt.date, rnd: random.Random | None = None) -> str:
    """Sorteia a categoria do dia (pelos pesos), fora das que saíram nos últimos `nao_repetir_categoria_dias`."""
    tcfg = cfg["tema"]
    cats = tcfg.get("categorias") or {}
    if not cats:
        return ""
    rnd = rnd or random.Random(f"{hoje.isoformat()}-{cfg.get('formato', '')}")
    dias = int(tcfg.get("nao_repetir_categoria_dias", 2))
    recentes = set()
    for h in hist:
        try:
            d = dt.date.fromisoformat(h["data"])
        except Exception:
            continue
        if 0 <= (hoje - d).days <= dias:
            recentes.add(h.get("categoria") or categoria_de(h.get("tema_pesquisa") or h.get("tema") or "", cats))
    livres = [n for n in cats if n not in recentes] or list(cats)
    pesos = [max(float((cats[n] or {}).get("peso", 1)), 0.01) for n in livres]
    return rnd.choices(livres, weights=pesos)[0]


def aplicar_categoria(cfg: dict, nome: str, rnd: random.Random | None = None) -> None:
    """Põe a categoria em cfg: rótulo vira o nicho do dia, buscas dela + gerais, reserva dela (embaralhada) antes das outras."""
    tcfg = cfg["tema"]
    cats = tcfg.get("categorias") or {}
    c = cats.get(nome) or {}
    rnd = rnd or random.Random(nome)
    base_b = tcfg.setdefault("_buscas_base", list(tcfg.get("buscas") or []))
    base_r = tcfg.setdefault("_reserva_base", list(tcfg.get("temas_reserva") or []))
    propria = list(c.get("temas_reserva") or [])
    rnd.shuffle(propria)
    outras = [t for n, o in cats.items() if n != nome for t in ((o or {}).get("temas_reserva") or [])]
    rnd.shuffle(outras)
    tcfg["categoria"] = nome
    tcfg["nicho"] = c.get("rotulo") or nome
    tcfg["buscas"] = list(dict.fromkeys(list(c.get("buscas") or []) + base_b))
    tcfg["temas_reserva"] = list(dict.fromkeys(propria + base_r + outras))


def temas_novos(cfg: dict, hist: list, hoje: dt.date, dias: int) -> list:
    """Sem referência do YouTube e com a reserva esgotada: a IA sugere temas inéditos (fora dos últimos 30 dias)."""
    tcfg = cfg["tema"]
    usados = [h.get("tema", "") for h in hist if h.get("data", "") >= (hoje - dt.timedelta(days=30)).isoformat()]
    prompt = f"""Sugira 8 temas para vídeos curtos de um canal brasileiro sobre {tcfg.get('nicho', 'IA e tecnologia')}.
Cada tema: até 8 palavras em PT-BR, explicável com números checáveis em fontes confiáveis (estudos, relatórios, notícias).
Variedade: nada de energia/data centers se já foi usado. NÃO repita nem parafraseie estes temas já usados: {json.dumps(usados, ensure_ascii=False)}
Responda SOMENTE um array JSON de strings."""
    try:
        lst, _, _ = gerar_json(prompt, cfg, temperatura=0.8)
    except Exception as e:
        nota(f"A IA não sugeriu temas novos ({str(e)[:100]}).")
        return []
    return [t.strip() for t in lst if isinstance(t, str) and t.strip() and not _repetido(t, hist, hoje, dias)
            and not _cansado(t, tcfg, hist, hoje)]


def temas_reserva(cfg: dict, hist: list, hoje: dt.date) -> list:
    """Ordem de tentativa quando o YouTube não traz referência: reserva não usada nos últimos dias;
    se esgotou, temas novos da IA; por último, a reserva do menos usado recentemente para o mais (nunca o de ontem primeiro)."""
    tcfg = cfg["tema"]
    dias = int(tcfg.get("nao_repetir_dias", 7))
    todos = list(dict.fromkeys(tcfg.get("temas_reserva") or []))
    livres = [t for t in todos if not _repetido(t, hist, hoje, dias) and not _cansado(t, tcfg, hist, hoje)]
    if livres and tcfg.get("categoria"):  # a ordem já vem sorteada pela categoria do dia
        return livres
    if livres:
        idx = hoje.toordinal() % len(livres)
        return livres[idx:] + livres[:idx]
    nota(f"Todos os temas de reserva foram usados nos últimos {dias} dias; pedi temas novos à IA.")
    novos = temas_novos(cfg, hist, hoje, dias)
    return novos + sorted([t for t in todos if not _cansado(t, tcfg, hist, hoje)] or todos, key=lambda t: _ultimo_uso(t, hist))


def _fmt(n):
    if n is None:
        return "n/d"
    if n >= 1e6:
        return f"{n / 1e6:.2f} mi".replace(".", ",")
    if n >= 1e3:
        return f"{n / 1e3:.0f} mil"
    return str(n)


def _pct(x):
    return "n/d" if x is None else f"{x * 100:.2f}%".replace(".", ",")


def pesquisar(cfg: dict, hist: list, hoje: dt.date) -> dict:
    tcfg = cfg["tema"]
    dias = int(tcfg.get("nao_repetir_dias", 7))
    if (tcfg.get("tema_fixo") or "").strip():
        t = tcfg["tema_fixo"].strip()
        nota(f"Pesquisa no YouTube pulada: tema fixo \"{t}\" escolhido na execução.")
        return {"ranking": [{"tema": t, "titulo": "", "url": "", "fixo": True}], "md": f"# Pesquisa\n\nTema fixo: {t}\n",
                "md_vencedor": f"**Tema fixo:** {t}"}
    cat = escolher_categoria(cfg, hist, hoje)
    if cat:
        aplicar_categoria(cfg, cat, random.Random(f"{hoje.isoformat()}-{cfg.get('formato', '')}-{cat}"))
        log(f"categoria do dia: {tcfg['nicho']} ({cat})")
        nota(f"Categoria sorteada hoje: {tcfg['nicho']}.")
    buscas = list(dict.fromkeys(list(tcfg.get("buscas", [])) + list(tcfg.get("buscas_extras") or [])))
    if len(buscas) < 12:
        nota(f"Só {len(buscas)} buscas configuradas (o prompt mestre pede pelo menos 12).")
    janela = int(tcfg.get("janela_dias", 15))
    cands, origem = [], ""
    key, origem_api = chave("YOUTUBE_API_KEY"), "YouTube Data API"
    if not key and chave("YT_REFRESH_TOKEN"):  # sem chave de API: usa a autorização do canal (escopo youtube.readonly)
        try:
            from .youtube import _token
            key, origem_api = "Bearer " + _token(), "YouTube Data API (autorização do canal)"
        except Exception as e:
            nota(f"Não consegui usar a autorização do canal na pesquisa ({str(e)[:100]}).")
    if key:
        try:
            cands, origem = via_api(buscas, janela, int(tcfg.get("candidatos_por_busca", 20)), key), origem_api
        except Exception as e:
            nota(f"YouTube Data API falhou ({str(e)[:120]}); tentei as páginas públicas.")
    if not cands:
        try:
            cands, origem = via_paginas(buscas, int(tcfg.get("candidatos_por_busca", 20))), "páginas públicas do YouTube"
        except Exception as e:
            nota(f"Leitura das páginas do YouTube falhou ({str(e)[:120]}).")
    log(f"pesquisa: {len(cands)} vídeos via {origem or 'nenhuma fonte'}")
    corte = hoje - dt.timedelta(days=janela)
    janela_ok = []
    for c in cands:
        try:
            if dt.date.fromisoformat(c["publicado"]) >= corte:
                janela_ok.append(c)
        except Exception:
            pass
    janela_ok.sort(key=lambda c: c["views"], reverse=True)
    janela_ok = janela_ok[:40]

    excluidos = []
    if janela_ok:
        recentes = [h["tema"] for h in hist if (hoje - dt.date.fromisoformat(h["data"])).days <= dias]
        lista = "\n".join(f'- id={c["id"]} | título="{c["titulo"]}" | canal="{c["canal"]}" | {c["views"]} views | {c["duracao_s"]}s | desc="{c["descricao"][:140]}"'
                          for c in janela_ok)
        prompt = f"""Você faz a triagem de referências para um canal brasileiro de vídeos sobre {tcfg.get('nicho', 'IA e tecnologia')} feitos com animação em código (motion graphics, sem rosto).
Temas usados nos últimos {dias} dias (não podem repetir): {json.dumps(recentes, ensure_ascii=False)}

Para CADA vídeo abaixo, responda um objeto JSON com:
id; marca_empresa (true se o canal é de marca/empresa/veículo corporativo: Google, OpenAI, Anthropic, BBC, CNBC, etc.);
filme_trailer_infantil (true se é filme, trailer, desenho ou conteúdo infantil); titulo_ingles (true se o título está em inglês);
fora_do_nicho (true se o assunto principal não é {tcfg.get('nicho', 'IA e tecnologia')}); tema_pt (o tema em até 8 palavras em PT-BR);
tema_repetido (true se é o mesmo assunto de algum tema usado); formato_bate (true se é vídeo explicativo/animado/motion graphics, o nosso formato);
verificavel (true se o tema pode ser recontado com números checáveis em fontes confiáveis);
d (0-10: facilidade de recontar em PT-BR, tema universal, sem trocadilho intraduzível, sem depender de rosto ou cena real) e motivo_d (uma linha);
e (0-10: indício de retenção pela duração adequada, ritmo e tema; é estimativa) e motivo_e (uma linha).
Responda SOMENTE um array JSON.

Vídeos:
{lista}"""
        try:
            cls, _, _ = gerar_json(prompt, cfg, temperatura=0.2)
            mapa = {x.get("id"): x for x in cls if isinstance(x, dict)}
        except Exception as e:
            nota(f"Triagem por IA falhou ({str(e)[:100]}); usei só as métricas.")
            mapa = {}
        validos = []
        for c in janela_ok:
            x = mapa.get(c["id"], {})
            c.update({k: x.get(k) for k in ("tema_pt", "formato_bate", "verificavel", "d", "e", "motivo_d", "motivo_e")})
            motivo = None
            if x.get("marca_empresa"):
                motivo = "marca/empresa"
            elif x.get("filme_trailer_infantil"):
                motivo = "filme/trailer/infantil"
            elif x and not x.get("titulo_ingles", True):
                motivo = "título fora do inglês"
            elif x.get("fora_do_nicho"):
                motivo = "fora do nicho"
            elif x.get("tema_repetido") or _repetido(c.get("tema_pt") or c["titulo"], hist, hoje, dias):
                motivo = f"tema repetido (últimos {dias} dias)"
            elif _cansado(c.get("tema_pt") or c["titulo"], tcfg, hist, hoje):
                motivo = "assunto saturado no canal (energia/data center)"
            if motivo:
                excluidos.append((c, motivo))
                continue
            notas_metricas(c)
            c["d"] = float(c.get("d") or 5)
            c["e"] = float(c.get("e") or 5)
            c["total"] = round(c["nota_a"] + c["nota_b"] + c["nota_c"] + c["d"] + c["e"], 1)
            c["tema"] = c.get("tema_pt") or c["titulo"]
            validos.append(c)
        # CRIVO 2: verificável primeiro
        validos.sort(key=lambda c: (bool(c.get("verificavel", True)), c["total"]), reverse=True)
    else:
        validos = []

    if not validos:
        nota("Nenhuma referência do YouTube passou no CRIVO 1 hoje; usei a lista de temas de reserva.")
        ordem = temas_reserva(cfg, hist, hoje)
        return {"ranking": [{"tema": t, "titulo": "", "url": "", "reserva": True} for t in ordem],
                "md": "# Pesquisa\n\nSem referências válidas hoje; tema da lista de reserva.\n", "md_vencedor": f"**Tema de reserva:** {ordem[0] if ordem else ''}"}

    top = validos[:10]
    linhas = lambda xs: [f"| {i} | [{c['titulo'][:70].replace('|', '/')}]({c['url']}) | {c['canal']} ({_fmt(c.get('inscritos'))}) | {c['publicado']} | "
                         f"{_fmt(c['views'])} | {('%.1f×' % c['views_insc']).replace('.', ',') if c.get('views_insc') else 'n/d'} | {_pct(c['curt_views'])} | "
                         f"{_pct(c['coment_views'])} | {c['duracao_s'] // 60} min | {c['total']} |" for i, c in xs]
    cab = ["| # | Vídeo | Canal (inscritos) | Publicado | Views | Views/insc. | Curt./views | Coment./views | Dur. | Nota |", "|---|---|---|---|---|---|---|---|---|---|"]
    numerados = list(enumerate(top, 1))
    md = [f"# Pesquisa de referências — {hoje.strftime('%d/%m/%Y')}", "",
          f"{len(buscas)} buscas em inglês ({origem}): " + ", ".join(buscas) + f". Janela: publicados desde {corte.strftime('%d/%m/%Y')} (pela data exata de publicação).", "",
          "## Top 10 — o formato bate", ""] + cab + linhas([x for x in numerados if x[1].get("formato_bate")]) + \
         ["", "## Top 10 — só o tema bate", ""] + cab + linhas([x for x in numerados if not x[1].get("formato_bate")]) + \
         ["", "## Excluídos pelo CRIVO 1 ou pelo veto de tema", ""] + [f"- {c['titulo'][:80]} ({c['canal']}): {m}" for c, m in excluidos[:30]] + \
         ["", "## Notas (0–10) dos 3 primeiros", "", "| Critério | " + " | ".join(c['canal'] for c in top[:3]) + " |", "|---|" + "---|" * len(top[:3])]
    for k, nome in (("nota_a", "(a) views absolutas"), ("nota_b", "(b) curtidas e comentários"), ("nota_c", "(c) inscritos e views/inscritos"),
                    ("d", "(d) facilidade de recontar em PT-BR"), ("e", "(e) retenção (estimativa)")):
        extra = lambda c: (f": {c.get('motivo_' + k)}" if k in ("d", "e") and c.get("motivo_" + k) else "")
        md.append(f"| {nome} | " + " | ".join(f"{c[k]}{extra(c)}" for c in top[:3]) + " |")
    md.append("| **Total** | " + " | ".join(f"**{c['total']}**" for c in top[:3]) + " |")
    v = top[0]
    md_v = "\n".join(["## Vencedor da pesquisa", "", "| | Vídeo | Views | Views/insc. | Curt./views | Coment./views | Nota |", "|---|---|---|---|---|---|---|"] +
                     [f"| {i} | [{c['titulo'][:60].replace('|', '/')}]({c['url']}) ({c['canal']}) | {_fmt(c['views'])} | "
                      f"{('%.1f×' % c['views_insc']).replace('.', ',') if c.get('views_insc') else 'n/d'} | {_pct(c['curt_views'])} | {_pct(c['coment_views'])} | {c['total']} |"
                      for i, c in enumerate(top[:3], 1)] + ["", "Copiamos só o TEMA e o FORMATO, nunca o conteúdo. Tabela completa em `pesquisa.md`."])
    log(f"vencedor provisório: {v['titulo']} ({v['total']})")
    return {"ranking": validos, "top10": top, "md": "\n".join(md) + "\n", "md_vencedor": md_v, "origem": origem}
