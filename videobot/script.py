"""Etapa 3 (parte 2): roteiro + cenas + pacote de publicação, com validação dos CRIVOs em código."""
from __future__ import annotations

import json
import re

from .facts import valores
from .llm import gerar_json
from .objetos3d import prompt_catalogo
from .util import log, nota, slugify

TEMPLATES = """CATÁLOGO DE CENAS (campo "template" + "params"). Use variedade; nunca 3 iguais seguidas.
- headline: {"eyebrow"?: str curto, "text": str (até 9 palavras), "highlight": [palavras do text], "icon"?: ICONE, "sub"?: str}
- bignumber: {"label": str, "value": número, "prefix"?: "US$ ", "suffix"?: " bi"|" mi"|"%"|" m²"..., "decimals"?: int, "sub": str, "icon"?: ICONE}
- compare: {"title"?: str, "left": {"label","value","prefix"?,"suffix"?,"decimals"?,"note"?,"tone": "good"|"bad"|"neutral"}, "right": {...}, "winner"?: "left"|"right"}
- list: {"title": str, "items": [2 a 5 frases curtas], "numbered"?: bool}
- bars: {"title": str, "prefix"?, "suffix"?, "decimals"?, "bars": [{"label": str, "value": número, "highlight"?: bool}] (2 a 6)}
- quote: {"text": str, "author": str, "role": str, "paraphrase": bool}  (paraphrase=true se não for citação literal da fonte)
- timeline: {"title": str, "events": [{"date": str, "label": str}] (2 a 5)}
- kpis: {"title"?: str, "items": [{"value": número, "prefix"?, "suffix"?, "decimals"?, "label": str, "icon"?: ICONE}] (2 a 4)}
- chat: {"prompt": str, "answer": str, "app"?: str}  (interface de assistente de IA; ilustrativa)
- icons: {"title"?: str, "items": [{"icon": ICONE, "label": str}] (2 a 4)}
- question: {"text": str, "highlight": [..], "options"?: [2 opções curtas]}
- gauge: {"value": 0-100, "label": str, "sub"?: str}
- flow: {"title"?: str, "steps": [{"label": str, "icon"?: ICONE}] (2 a 4)}
- cta: {"text": str, "highlight": [..], "options"?: [2 opções binárias], "kind"?: "comment"|"subscribe"}
ICONE ∈ ia, chip, robot, rocket, satellite, globe, money, coin, bolt, warning, chart, trendup, trenddown, server, check, cross, clock, calendar,
user, users, building, gov, lock, sun, fire, thermo, snow, cloud, code, phone, laptop, search, doc, scale, target, play, battery, leaf, heart,
eye, signal, chat, water, car, game, music, shield, question, bubble, factory"""

NOMES = {"headline", "statement", "bignumber", "compare", "list", "bars", "quote", "timeline", "kpis", "chat", "icons", "question", "gauge", "flow", "cta"}


def _alvos(cfg):
    if cfg["formato"] == "curto":
        s = float(cfg["duracao"].get("curto_seg", 65))
        alvo = int(s * 2.6)
        return {"palavras": (max(120, alvo - 25), alvo + 15), "cenas": (8, 10), "caps": (1, 1), "seg": s}
    m = float(cfg["duracao"].get("longo_min", 7))
    alvo = int(m * 155)
    lo, hi = max(900, alvo - 120), min(1400, alvo + 120) if m <= 9 else 1400
    return {"palavras": (min(lo, hi - 50), hi), "cenas": (18, 40), "caps": (5, 8), "seg": m * 60}


def _prompt(cand, fatos, cfg, hoje, alvos, erros=None, anterior=None):
    curto = cfg["formato"] == "curto"
    fl = "\n".join(f'[{f["id"]}] {f["afirmacao"]} | números na fonte: {", ".join(f.get("numeros") or []) or "—"} | {f["fonte"]}, {f.get("data", "")} | lado: {f.get("lado", "")}'
                   for f in fatos["fatos"])
    regras_formato = (
        f"CURTO (9:16): UM capítulo só, {alvos['cenas'][0]} a {alvos['cenas'][1]} cenas, {alvos['palavras'][0]} a {alvos['palavras'][1]} palavras no total "
        f"(~{int(alvos['seg'])} s). Cena 1 = gancho de até 3 s (pergunta ou número chocante). Última cena = CTA pedindo comentário BINÁRIO (template cta com options)."
        if curto else
        f"LONGO (16:9): {alvos['caps'][0]} a {alvos['caps'][1]} capítulos com títulos curtos (o 1º é a intro, sem cartela), {alvos['palavras'][0]} a {alvos['palavras'][1]} palavras "
        f"no total (~{alvos['seg'] / 60:.0f} min). Gancho nos primeiros 15 s. Termine cada capítulo com um 'loop aberto' que puxa o próximo. "
        "CTA no meio (pedir inscrição/comentário, template cta) e no fim (comentário binário). Cada cena tem 25 a 60 palavras de narração.")
    p = f"""Você é roteirista de um canal brasileiro de vídeos sobre {cfg['tema'].get('nicho', 'IA e tecnologia')}, narrados por voz e animados em código (motion graphics escuro, estilo estúdio).
Data de hoje: {hoje.strftime('%d/%m/%Y')}. Tema: "{fatos['tema']}". Ângulo: {fatos.get('angulo', '')}.
{('Referência (copie só TEMA e FORMATO, nunca o conteúdo): "' + cand['titulo'] + '"') if cand.get('titulo') else ''}

FATOS VERIFICADOS (use SOMENTE estes números; cite os ids em fact_ids):
{fl}

REGRAS DO ROTEIRO
- {regras_formato}
- Narração em PT-BR natural, frases curtas, tom curioso e levemente irônico. Escreva TODOS os números por extenso como se fala ("dois vírgula um trilhões", "dois mil e vinte e oito"); nada de algarismos na narração. Escreva "IA", nunca "I.A.".
- Toda afirmação com número precisa vir de um fato da lista (fact_ids). Sem fato, sem número. Não invente nada.
- Inclua o contraponto (o outro lado). {'O tema é de finanças: inclua o aviso "não é recomendação de investimento".' if fatos.get('financas') else ''}
- Não diga que conteúdo sintético é real. Interfaces de chat são ilustrativas.
- Os "params" das cenas são o que aparece na tela: números com algarismos (ex.: value 2.1, suffix " tri"), sempre iguais aos dos fatos citados. Textos de tela curtos.

{TEMPLATES}

{prompt_catalogo()}

PUBLICAÇÃO
- youtube.titulo: até 70 caracteres, palavra-chave no começo, número ou pergunta, no máximo 1 emoji{', terminando com #shorts' if curto else ''}. 3 alternativos para A/B.
- youtube.abertura: 2 linhas com gancho e palavra-chave. topicos: 4 a 6 linhas começando com emoji. cta: pergunta de comentário. aviso: '' ou aviso de finanças/IA.
- youtube.hashtags: 3 a 5. youtube.tags: 18 a 24 tags (PT-BR amplas e de cauda longa + 2 ou 3 em inglês), total até 480 caracteres.
- youtube.comentario_fixado: pergunta binária. youtube.sintetico: {{"resposta":"Sim|Não","motivo":"..."}} (animação claramente não realista e voz genérica → Não, salvo se houver algo realista). categoria. horario (sugestão para o Brasil).
- tiktok.legenda (até 150 caracteres visíveis, gancho + CTA, sem as hashtags), tiktok.hashtags (3 a 5: 1 ampla, 2 de nicho, 1 em alta), tiktok.capa (até 4 palavras), tiktok.primeira_frase,
  tiktok.rotulo_ia {{"resposta":"Sim","motivo":"narração com voz sintética"}}, tiktok.som, tiktok.horario.
- thumb: {{"lines": [{{"text": "ATÉ 2 PALAVRAS"}}, {{"text": "ATÉ 2 PALAVRAS", "hl": true}}], "number": "um número dos fatos, com algarismos", "numberLabel": "até 4 palavras", "icon": ICONE}} — no máximo 4 palavras grandes no total.

Responda SOMENTE com JSON:
{{"tema": "...", "chapters": [{{"title": "...", "scenes": [{{"id": "slug_unico", "text": "narração", "template": "...", "params": {{...}}, "objetos3d": ["id do catálogo 3D", "..."], "fact_ids": [1,2]}}]}}],
 "thumb": {{...}}, "publicacao": {{"youtube": {{...}}, "tiktok": {{...}}}}}}"""
    if erros:
        p += "\n\nSEU ROTEIRO ANTERIOR TEVE ESTES PROBLEMAS. Corrija todos e devolva o JSON completo:\n- " + "\n- ".join(erros[:40])
        p += "\n\nROTEIRO ANTERIOR:\n" + json.dumps(anterior, ensure_ascii=False)[:60000]
    return p


def _numeros_params(o) -> list[float]:
    out = []
    if isinstance(o, bool):
        return out
    if isinstance(o, (int, float)):
        return [float(o)]
    if isinstance(o, str):
        return sorted(valores(o)) if re.search(r"\d", o) else []
    if isinstance(o, dict):
        for k, v in o.items():
            if k in ("decimals", "numbered", "paraphrase", "highlight", "tone", "winner", "kind", "icon"):
                continue
            out += _numeros_params(v)
    if isinstance(o, list):
        for v in o:
            out += _numeros_params(v)
    return out


def validar(r: dict, fatos: dict, cfg: dict, hoje) -> list[str]:
    alvos = _alvos(cfg)
    err = []
    chs = r.get("chapters") or []
    cenas = [sc for ch in chs for sc in ch.get("scenes", [])]
    if not cenas:
        return ["roteiro sem cenas"]
    n_pal = sum(len(sc.get("text", "").split()) for sc in cenas)
    if not alvos["palavras"][0] <= n_pal <= alvos["palavras"][1]:
        err.append(f"o roteiro tem {n_pal} palavras; precisa ter entre {alvos['palavras'][0]} e {alvos['palavras'][1]}")
    if cfg["formato"] == "curto":
        if not alvos["cenas"][0] <= len(cenas) <= alvos["cenas"][1]:
            err.append(f"o curto tem {len(cenas)} cenas; precisa de {alvos['cenas'][0]} a {alvos['cenas'][1]}")
    elif not alvos["caps"][0] <= len(chs) <= alvos["caps"][1]:
        err.append(f"o longo tem {len(chs)} capítulos; precisa de {alvos['caps'][0]} a {alvos['caps'][1]}")
    por_id = {f["id"]: f for f in fatos["fatos"]}
    ids = set()
    for sc in cenas:
        sid = sc.get("id", "")
        if not sid or sid in ids:
            err.append(f"id de cena vazio ou repetido: '{sid}'")
        ids.add(sid)
        tx = sc.get("text", "")
        if re.search(r"\d", tx):
            achados = re.findall(r"[\d.,%]+", tx)[:3]
            err.append(f"cena {sid}: a narração tem algarismos ({achados}); escreva por extenso")
        if "I.A." in tx:
            err.append(f"cena {sid}: escreva IA, não I.A.")
        if sc.get("template") not in NOMES:
            err.append(f"cena {sid}: template '{sc.get('template')}' não existe")
        nums = _numeros_params(sc.get("params", {}))
        if nums:
            base = set()
            for fid in sc.get("fact_ids", []):
                f = por_id.get(fid)
                if f:
                    base |= valores(" ".join(f.get("numeros") or []) + " " + f["afirmacao"])
            base |= {float(hoje.year)}
            for x in nums:
                if not any(x == b or (b and abs(x - b) / abs(b) < 0.011) or (b and abs(x * 1e9 - b) / abs(b) < 0.011)
                           or (b and abs(x * 1e6 - b) / abs(b) < 0.011) or (b and abs(x * 1e12 - b) / abs(b) < 0.011) or (b and abs(x * 1e3 - b) / abs(b) < 0.011)
                           for b in base):
                    err.append(f"cena {sid}: o número {x:g} na tela não está nos fatos citados {sc.get('fact_ids', [])}")
    if not r.get("thumb", {}).get("lines"):
        err.append("faltou o objeto thumb")
    else:
        pal = sum(len(l.get("text", "").split()) for l in r["thumb"]["lines"])
        if pal > 4:
            err.append(f"a thumb tem {pal} palavras grandes; máximo 4")
    yt = (r.get("publicacao") or {}).get("youtube") or {}
    titulo = yt.get("titulo")
    if isinstance(titulo, list):  # alguns modelos mandam várias opções; a 1ª vira o título (publish.normalizar_publicacao)
        titulo = str(titulo[0]) if titulo else ""
    if not titulo:
        err.append("faltou publicacao.youtube.titulo")
    elif len(titulo) > 70:
        err.append(f"título com {len(titulo)} caracteres; máximo 70")
    if not (r.get("publicacao") or {}).get("tiktok"):
        err.append("faltou publicacao.tiktok")
    return err


def _sanear(r: dict, fatos: dict, cfg, hoje):
    """Último recurso: cena com número fora dos fatos vira título sem número."""
    por_id = {f["id"]: f for f in fatos["fatos"]}
    for ch in r["chapters"]:
        for sc in ch["scenes"]:
            if sc.get("template") not in NOMES:
                sc["template"] = "headline"
            sc["text"] = sc["text"].replace("I.A.", "IA")
            e = validar({"chapters": [{"title": "x", "scenes": [sc]}], "thumb": {"lines": [{"text": "x"}]},
                         "publicacao": {"youtube": {"titulo": "x"}, "tiktok": {"x": 1}}}, fatos, dict(cfg, formato="__"), hoje)
            if any("não está nos fatos" in x for x in e):
                nota(f"Cena {sc['id']}: número na tela sem fato correspondente; troquei por título sem número.")
                sc["template"], sc["params"] = "headline", {"text": ch["title"], "eyebrow": cfg["tema"].get("nicho", "")}
    return r


def escrever(cand: dict, fatos: dict, cfg: dict, hoje) -> dict:
    alvos = _alvos(cfg)
    r, _, modelo = gerar_json(_prompt(cand, fatos, cfg, hoje, alvos), cfg, temperatura=0.7)
    erros = validar(r, fatos, cfg, hoje)
    for rodada in range(2):
        if not erros:
            break
        log(f"roteiro: {len(erros)} problema(s); pedindo correção ({rodada + 1}/2)")
        r2, _, modelo = gerar_json(_prompt(cand, fatos, cfg, hoje, alvos, erros, r), cfg, temperatura=0.4)
        e2 = validar(r2, fatos, cfg, hoje)
        if len(e2) <= len(erros):
            r, erros = r2, e2
    if erros:
        nota("Roteiro: pendências após 2 correções: " + "; ".join(erros[:6]))
        r = _sanear(r, fatos, cfg, hoje)
    # fonte no rodapé de cada cena = fatos citados (montada em código, não pelo modelo)
    por_id = {f["id"]: f for f in fatos["fatos"]}
    for ch in r["chapters"]:
        for sc in ch["scenes"]:
            fs = [por_id[i] for i in sc.get("fact_ids", []) if i in por_id]
            vistos, partes = set(), []
            for f in fs:
                if f["fonte"] not in vistos:
                    vistos.add(f["fonte"]); partes.append(f"{f['fonte']}, {f.get('data', '')}".strip(", "))
            sc["source"] = "; ".join(partes[:2])
            sc["id"] = slugify(sc.get("id", "c"), 30)
    r["formato"] = cfg["formato"]
    r["tema"] = r.get("tema") or fatos["tema"]
    r["slug"] = slugify(r["tema"])
    r["modelo_roteiro"] = modelo
    n_pal = sum(len(sc["text"].split()) for ch in r["chapters"] for sc in ch["scenes"])
    log(f"roteiro pronto ({modelo}): {len(r['chapters'])} capítulo(s), {sum(len(c['scenes']) for c in r['chapters'])} cenas, {n_pal} palavras")
    return r
