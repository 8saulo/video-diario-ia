"""Etapa 3 (parte 2): roteiro + cenas + pacote de publicação, com validação dos CRIVOs em código."""
from __future__ import annotations

import json
import re

from .facts import valores
from .llm import gerar_json, objeto
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

# Voz padrão de todos os vídeos (aprovada no capítulo 2 do longo do IPO da Anthropic, 22/11): apresentador expressivo,
# com emoção contida e real. As tags de emoção de cada cena saem deste vocabulário e passam por emocoes_coerentes().
EMOCOES_LISTA = ("curioso, intrigante", "didático, acolhedor", "interessado, explicativo", "firme, analítico",
                 "enfático no número", "surpresa contida", "otimista, caloroso", "grave, cauteloso", "reflexivo",
                 "cordial e direto")
EMOCOES_PADRAO = """DIREÇÃO DE VOZ (campo "emocao" em cada cena, use EXATAMENTE uma destas tags): apresentador expressivo, com emoção
contida e real; a tag precisa combinar com o que a frase diz e VARIAR de cena para cena (nunca a mesma em mais de 2 cenas seguidas):
- "curioso, intrigante": gancho e perguntas ao espectador;
- "didático, acolhedor": quando explica um conceito ou termo;
- "interessado, explicativo": contexto e desenvolvimento da história;
- "firme, analítico": argumentos, comparações e consequências;
- "enfático no número": a cena do dado mais importante (no máximo 1 a cada 4 cenas);
- "surpresa contida": a virada, o detalhe inesperado;
- "otimista, caloroso": conquista ou boa notícia;
- "grave, cauteloso": riscos, perdas, críticas, problemas;
- "reflexivo": conclusão e o que observar daqui para a frente;
- "cordial e direto": pedidos de comentário/inscrição (CTA).
Nunca eufórico, teatral, irônico, urgente ou gritando."""

# Estilo do roteiro (config: roteiro.estilo). "viral" é o de sempre; "educativo" é o de apresentador de jornal
# financeiro/tecnológico: explica, contextualiza e conta a história com calma (pauta do IPO da Anthropic, 22/11).
ESTILOS = {
    "viral": {
        "narrativa": """NARRATIVA (o mais importante): conte uma HISTÓRIA, não uma lista de manchetes.
- GANCHO (cena 1, no máximo 9 palavras, ~3 s): o ponto mais intrigante — um conflito, um mistério, uma consequência para quem assiste
  ou uma pergunta que exige resposta. Ele cria uma pergunta na cabeça do espectador.
- DESENVOLVIMENTO: cada cena nasce da anterior e abre a próxima, com conectivos naturais de quem conta um caso ("só que...",
  "e aí...", "o problema é que...", "mas tem um detalhe...", "e foi aí que..."). Contexto rápido (quem/o quê, por que importa),
  depois uma VIRADA no meio. Os fatos e números entram como PROVAS dentro da história, nunca em sequência solta.
- DESFECHO: responde a pergunta do gancho (fecha o ciclo), traz a consequência para o espectador e só então o CTA.
- Teste: lido em voz alta, tem que soar como um amigo contando um caso curioso, não como leitura de jornal.""",
        "tom": """- Narração em PT-BR falado, como um criador de shorts conversando com o espectador ("você"): frases curtas (até 12 palavras),
  ritmo de corte rápido, contraste e surpresa ("parece muito? espera."), perguntas retóricas, uma revelação por cena,
  verbos fortes, nada de linguagem de relatório. Tom curioso, empolgado e levemente irônico. Use "!" e "?" para guiar a entonação
  e reticências ("...") para uma pausa dramática antes de um número ou revelação (no máximo 1 por cena).""",
        "emocoes": EMOCOES_PADRAO,
        "critico": "editor-chefe de vídeos curtos virais",
    },
    "educativo": {
        "narrativa": """NARRATIVA (o mais importante): um vídeo EXPLICATIVO e EDUCATIVO com enredo, em quatro partes que fluem uma na outra.
- GANCHO (cena 1, no máximo 9 palavras, ~3 s): a pergunta ou o fato central que o vídeo vai responder. Intrigante, mas sóbrio,
  sem sensacionalismo.
- INTRODUÇÃO: situe o espectador. Quem é, o que aconteceu ou vai acontecer, por que isso importa para ele. Explique em uma frase
  simples todo termo técnico na primeira vez que aparecer (ex.: o que é um IPO, o que é valor de mercado, o que é receita anual).
- DESENVOLVIMENTO: a história contada em ordem lógica (antes → agora → o que muda), cada cena nascendo da anterior com conectivos
  de explicação ("para entender isso...", "o ponto é que...", "e aqui está a virada...", "na prática, isso significa..."). Os números
  entram como PROVAS do raciocínio, sempre com o contexto que dá sentido a eles (comparação, escala, prazo). Há uma VIRADA no meio:
  o detalhe que muda a leitura do assunto. Traga o outro lado (riscos, críticas, incertezas) de forma honesta.
- CONCLUSÃO: responda a pergunta do gancho, resuma em uma frase o que o espectador aprendeu e o que observar daqui para a frente.
- Teste: lido em voz alta, soa como um bom apresentador de telejornal de economia e tecnologia explicando com clareza, não como
  leitura de manchetes em sequência.""",
        "tom": """- Narração em PT-BR falado, no tom de um apresentador de jornal financeiro e tecnológico: sério, claro, seguro e didático, falando
  com o espectador ("você") com respeito. Frases curtas e completas (até 16 palavras), vocabulário preciso, sem gírias, sem ironia,
  sem exageros ("chocante", "inacreditável", "absurdo" estão proibidos). Pontuação sóbria: "?" só em perguntas reais, no máximo um
  "!" no vídeo todo, reticências só se a pausa for necessária (no máximo 2 no vídeo).""",
        "emocoes": EMOCOES_PADRAO,
        "critico": "editor-chefe de um telejornal de economia e tecnologia",
    },
}


_NEGATIVO = re.compile(r"(?<!\w)(risco|riscos|perda|perdas|prejuízo|preju[ií]zos?|queda|caiu|caíram|crise|bolha|demiss|ameaça|multa|"
                       r"processo|processad|crítica|críticas|problema|problemas|falha|falhou|déficit|dívida|incerte|alerta|cuidado)", re.I)
_POSITIVO = {"otimista, caloroso", "surpresa contida", "enfático no número"}
_SINONIMOS_EMO = {"empolg": "interessado, explicativo", "animad": "interessado, explicativo", "irôn": "firme, analítico",
                  "ironi": "firme, analítico", "urgent": "firme, analítico", "acelerand": "firme, analítico",
                  "espant": "surpresa contida", "surpres": "surpresa contida", "intrig": "curioso, intrigante",
                  "curios": "curioso, intrigante", "sério": "firme, analítico", "seri": "firme, analítico", "neutr": "interessado, explicativo",
                  "didát": "didático, acolhedor", "pausad": "didático, acolhedor", "caloros": "otimista, caloroso", "otimis": "otimista, caloroso",
                  "convida": "cordial e direto", "cordial": "cordial e direto", "reflex": "reflexivo", "grave": "grave, cauteloso",
                  "cautel": "grave, cauteloso", "preocup": "grave, cauteloso", "enfát": "enfático no número", "analít": "firme, analítico",
                  "firme": "firme, analítico", "explica": "interessado, explicativo"}
_ROTACAO = ("interessado, explicativo", "firme, analítico", "didático, acolhedor")


def _emocao_da_lista(e: str) -> str:
    e = str(e or "").strip().lower()
    for x in EMOCOES_LISTA:
        if e == x:
            return x
    for k, v in _SINONIMOS_EMO.items():
        if k in e:
            return v
    return ""


def emocoes_coerentes(r: dict) -> int:
    """Põe a tag de emoção de cada cena no momento certo do roteiro (em código; o modelo erra). Devolve quantas mudou.
    - só tags do vocabulário padrão (sinônimos viram a tag mais próxima; "empolgado"/"irônico" nunca passam);
    - CTA = "cordial e direto"; pergunta sem tag = "curioso, intrigante";
    - fala de risco/perda/crise com tag positiva = "grave, cauteloso";
    - "enfático no número" sem número na tela vira "firme, analítico";
    - nunca 3 cenas seguidas com a mesma tag."""
    cenas = [sc for ch in (r.get("chapters") or []) for sc in (ch.get("scenes") or []) if isinstance(sc, dict)]
    mudou, seguidas = 0, []
    for sc in cenas:
        antes = sc.get("emocao")
        tx = str(sc.get("text") or "")
        e = _emocao_da_lista(antes)
        if sc.get("template") == "cta":
            e = "cordial e direto"
        elif not e:
            e = "curioso, intrigante" if tx.rstrip().endswith("?") else "interessado, explicativo"
        if e in _POSITIVO and _NEGATIVO.search(tx):
            e = "grave, cauteloso"
        if e == "enfático no número" and sc.get("template") not in ("bignumber", "kpis", "bars", "gauge", "compare"):
            e = "firme, analítico"
        if len(seguidas) >= 2 and seguidas[-1] == seguidas[-2] == e and sc.get("template") != "cta":
            e = next(x for x in _ROTACAO if x != e)
        seguidas.append(e)
        if e != antes:
            sc["emocao"] = e
            mudou += 1
    return mudou


def nome_estilo(cfg: dict) -> str:
    nome = str(((cfg.get("roteiro") or {}).get("estilo")) or "viral").strip().lower()
    return nome if nome in ESTILOS else "viral"


def estilo(cfg: dict) -> dict:
    return ESTILOS[nome_estilo(cfg)]


def notas_da_pauta(cfg: dict) -> str:
    """Instruções extras do dia (config: roteiro.notas), ex.: o que explicar e o que não presumir."""
    n = str(((cfg.get("roteiro") or {}).get("notas")) or "").strip()
    return f"ORIENTAÇÕES DESTE VÍDEO (obrigatórias):\n{n}" if n else ""


NOMES = {"headline", "statement", "bignumber", "compare", "list", "bars", "quote", "timeline", "kpis", "chat", "icons", "question", "gauge", "flow", "cta"}


def licoes_do_canal() -> str:
    try:
        from .youtube import licoes
        return licoes()
    except Exception:
        return ""


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
    est = estilo(cfg)
    fl = "\n".join(f'[{f["id"]}] {f["afirmacao"]} | números na fonte: {", ".join(f.get("numeros") or []) or "—"} | {f["fonte"]}, {f.get("data", "")} | lado: {f.get("lado", "")}'
                   for f in fatos["fatos"])
    regras_formato = (
        f"CURTO (9:16): UM capítulo só, {alvos['cenas'][0]} a {alvos['cenas'][1]} cenas, {alvos['palavras'][0]} a {alvos['palavras'][1]} palavras no total "
        f"(~{int(alvos['seg'])} s). Cada cena tem cerca de {round(sum(alvos['palavras']) / 2 / sum(alvos['cenas']) * 2)} palavras de narração (2 ou 3 frases curtas): frases curtas NÃO significam roteiro curto; conte as palavras e respeite o total. Cena 1 = gancho de até 3 s (pergunta ou número chocante). Última cena = CTA pedindo comentário BINÁRIO (template cta com options)."
        if curto else
        f"LONGO (16:9): {alvos['caps'][0]} a {alvos['caps'][1]} capítulos com títulos curtos (o 1º é a intro, sem cartela), {alvos['palavras'][0]} a {alvos['palavras'][1]} palavras "
        f"no total (~{alvos['seg'] / 60:.0f} min). Gancho nos primeiros 15 s. Termine cada capítulo com um 'loop aberto' que puxa o próximo. "
        "CTA no meio (pedir inscrição/comentário, template cta) e no fim (comentário binário). Cada cena tem 25 a 60 palavras de narração.")
    p = f"""Você é roteirista de um canal brasileiro de vídeos sobre {cfg['tema'].get('nicho', 'IA e tecnologia')}, narrados por voz e animados em código (motion graphics escuro, estilo estúdio).
Data de hoje: {hoje.strftime('%d/%m/%Y')}. Tema: "{fatos['tema']}". Ângulo: {fatos.get('angulo', '')}.
{('Referência (copie só TEMA e FORMATO, nunca o conteúdo): "' + cand['titulo'] + '"') if cand.get('titulo') else ''}

FATOS VERIFICADOS (use SOMENTE estes números; cite os ids em fact_ids):
{fl}

{licoes_do_canal()}

{est["narrativa"]}

{notas_da_pauta(cfg)}

REGRAS DO ROTEIRO
- {regras_formato}
{est["tom"]}
- Escreva TODOS os números por extenso como se fala ("dois vírgula um trilhões", "dois mil e vinte e oito"); nada de algarismos na narração. Escreva "IA", nunca "I.A.".
- Toda afirmação com número precisa vir de um fato da lista (fact_ids). Sem fato, sem número. Não invente nada.
- Inclua o contraponto (o outro lado). {'O tema é de finanças: inclua o aviso "não é recomendação de investimento".' if fatos.get('financas') else ''}
- Não diga que conteúdo sintético é real. Interfaces de chat são ilustrativas.
- Os "params" das cenas são o que aparece na tela: números com algarismos (ex.: value 2.1, suffix " tri"), sempre iguais aos dos fatos citados. Textos de tela curtos.

{TEMPLATES}

{prompt_catalogo()}

{est["emocoes"]}

PUBLICAÇÃO
- youtube.titulo: até 70 caracteres, palavra-chave no começo, número ou pergunta, no máximo 1 emoji{', terminando com #shorts' if curto else ''}. 3 alternativos para A/B.
- youtube.abertura: 2 linhas com gancho e palavra-chave. topicos: 4 a 6 linhas começando com emoji. cta: pergunta de comentário. aviso: '' ou aviso de finanças/IA.
- youtube.hashtags: 3 a 5. youtube.tags: 18 a 24 tags (PT-BR amplas e de cauda longa + 2 ou 3 em inglês), total até 480 caracteres.
- youtube.comentario_fixado: pergunta binária. youtube.sintetico: {{"resposta":"Sim|Não","motivo":"..."}} (animação claramente não realista e voz genérica → Não, salvo se houver algo realista). categoria. horario (sugestão para o Brasil).
- tiktok.legenda (até 150 caracteres visíveis, gancho + termina exatamente com 'Comente!' (nunca 'sim ou não'), sem as hashtags), tiktok.hashtags (3 a 5: 1 ampla, 2 de nicho, 1 em alta), tiktok.capa (até 4 palavras), tiktok.primeira_frase,
  tiktok.rotulo_ia {{"resposta":"Sim","motivo":"narração com voz sintética"}}, tiktok.som, tiktok.horario.
- thumb: {{"lines": [{{"text": "ATÉ 2 PALAVRAS"}}, {{"text": "ATÉ 2 PALAVRAS", "hl": true}}], "number": "um número dos fatos, com algarismos", "numberLabel": "até 4 palavras", "icon": ICONE}} — no máximo 4 palavras grandes no total.

Responda SOMENTE com JSON:
{{"tema": "...", "chapters": [{{"title": "...", "scenes": [{{"id": "slug_unico", "text": "narração", "template": "...", "params": {{...}}, "objetos3d": ["id do catálogo 3D", "..."], "emocao": "direção de voz da cena, 2 a 5 palavras", "fact_ids": [1,2]}}]}}],
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


def normalizar_cena(sc: dict) -> dict:
    """Conserta tipos que os modelos às vezes devolvem trocados (no lugar, e devolve a cena).

    Ex.: "template": {"name": "bars", "params": {...}} em vez de "template": "bars" (derrubou o longo de 22/11).
    """
    t = sc.get("template")
    if isinstance(t, dict):
        extra = t.get("params")
        t = next((t[k] for k in ("name", "nome", "template", "type", "tipo", "id") if isinstance(t.get(k), str)), "")
        if isinstance(extra, dict) and not sc.get("params"):
            sc["params"] = extra
    elif isinstance(t, list):
        t = next((x for x in t if isinstance(x, str)), "")
    sc["template"] = str(t or "").strip().lower()
    if not isinstance(sc.get("params"), dict):
        sc["params"] = {}
    for k in ("id", "text", "emocao"):
        if k in sc and not isinstance(sc[k], str):
            sc[k] = "" if sc[k] is None else str(sc[k])
    f = sc.get("fact_ids", [])
    if not isinstance(f, list):
        f = [f]
    ids = []
    for x in f:
        try:
            ids.append(int(x))
        except (TypeError, ValueError):
            pass
    sc["fact_ids"] = ids
    return sc


def validar(r: dict, fatos: dict, cfg: dict, hoje) -> list[str]:
    alvos = _alvos(cfg)
    err = []
    if not isinstance(r, dict):
        return ['a resposta não veio como o objeto JSON pedido ({"tema": ..., "chapters": [...]}); devolva o objeto completo']
    chs = [ch for ch in (r.get("chapters") or []) if isinstance(ch, dict)] if isinstance(r.get("chapters"), list) else []
    cenas = [sc for ch in chs for sc in (ch.get("scenes") or []) if isinstance(sc, dict)]
    if not cenas:
        return ["roteiro sem cenas"]
    n_pal = sum(len(sc.get("text", "").split()) for sc in cenas)
    if not alvos["palavras"][0] <= n_pal <= alvos["palavras"][1]:
        err.append(f"o roteiro tem {n_pal} palavras; precisa ter entre {alvos['palavras'][0]} e {alvos['palavras'][1]}")
    if cfg["formato"] == "curto":
        if not alvos["cenas"][0] <= len(cenas) <= alvos["cenas"][1]:
            err.append(f"o curto tem {len(cenas)} cenas; precisa de {alvos['cenas'][0]} a {alvos['cenas'][1]}")
        n1 = len(cenas[0].get("text", "").split())
        if n1 > 12:  # o gancho precisa caber nos primeiros ~3 s
            err.append(f"a cena 1 (gancho) tem {n1} palavras; precisa ter no máximo 9 (cerca de 3 segundos) e prender na hora")
    elif not alvos["caps"][0] <= len(chs) <= alvos["caps"][1]:
        err.append(f"o longo tem {len(chs)} capítulos; precisa de {alvos['caps'][0]} a {alvos['caps'][1]}")
    por_id = {f["id"]: f for f in fatos["fatos"]}
    ids = set()
    for sc in cenas:
        normalizar_cena(sc)
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


def _prompt_critico(r: dict, cfg: dict | None = None) -> str:
    est = estilo(cfg or {})
    cenas = "\n".join(f'{i + 1}. {sc.get("text", "")}' for i, sc in enumerate(sc for ch in r.get("chapters", []) for sc in ch.get("scenes", [])))
    return f"""Você é {est["critico"]}. Avalie este roteiro (uma fala por cena, na ordem):
{cenas}

Dê notas de 0 a 10:
- gancho: a cena 1 prende nos primeiros 3 segundos (curiosidade, conflito ou consequência para quem assiste)?
- narrativa: é uma HISTÓRIA (cada cena nasce da anterior, com virada e desfecho que fecha o gancho) ou uma lista de manchetes?
- fluidez: soa natural falado em voz alta, com conectivos, sem frases de relatório?
E liste até 5 problemas CONCRETOS e acionáveis (cite a cena pelo número e diga como reescrever).
Responda SOMENTE com JSON: {{"gancho": n, "narrativa": n, "fluidez": n, "problemas": ["..."]}}"""


def revisar_narrativa(r, erros, cand, fatos, cfg, hoje, alvos):
    """Crítico (ideia do OpenReels): nota gancho/narrativa/fluidez; abaixo de 7, ou roteiro curto, uma reescrita dirigida.
    Também resolve o roteiro curto demais dizendo QUANTO e ONDE acrescentar (antes só se pedia 'corrija')."""
    try:
        nota_c, _, _ = gerar_json(_prompt_critico(r, cfg), cfg, temperatura=0.2, max_tokens=1200)
    except Exception:
        nota_c = {}
    nota_c = objeto(nota_c)
    notas = {k: float(nota_c.get(k) or 10) for k in ("gancho", "narrativa", "fluidez")}
    problemas = [str(p) for p in (nota_c.get("problemas") or [])][:5]
    cenas = [sc for ch in r.get("chapters", []) for sc in ch.get("scenes", [])]
    n_pal = sum(len(sc.get("text", "").split()) for sc in cenas)
    falta = alvos["palavras"][0] - n_pal
    pedidos = []
    if min(notas.values()) < 7:
        pedidos += [f"crítico: gancho {notas['gancho']:g}/10, narrativa {notas['narrativa']:g}/10, fluidez {notas['fluidez']:g}/10"] + problemas
    if falta > 0:
        k = max(1, round(falta / 20))
        pedidos.append(f"o roteiro tem {n_pal} palavras e precisa de pelo menos {alvos['palavras'][0]}: ACRESCENTE {k} cena(s) nova(s) de "
                       f"18 a 24 palavras no DESENVOLVIMENTO (antes do desfecho), aprofundando a história com os fatos ainda não usados, "
                       f"sem mexer no gancho; não encurte as outras cenas")
    log(f"crítico do roteiro: gancho {notas['gancho']:g}, narrativa {notas['narrativa']:g}, fluidez {notas['fluidez']:g}; "
        f"{n_pal} palavras" + ("" if pedidos else " — aprovado"))
    if not pedidos:
        return r, erros
    try:
        r2, _, _ = gerar_json(_prompt(cand, fatos, cfg, hoje, alvos, erros + pedidos, r), cfg, temperatura=0.4)
    except Exception:
        return r, erros
    e2 = validar(r2, fatos, cfg, hoje)
    n2 = sum(len(sc.get("text", "").split()) for ch in r2.get("chapters", []) for sc in ch.get("scenes", []))
    # aceita se não piorou a validação e (se faltava texto) chegou mais perto do tamanho certo
    if len(e2) <= len(erros) and (falta <= 0 or n2 > n_pal):
        log(f"crítico: roteiro reescrito ({n_pal} -> {n2} palavras)")
        return r2, e2
    return r, erros


def escrever(cand: dict, fatos: dict, cfg: dict, hoje) -> dict:
    alvos = _alvos(cfg)
    if cfg["formato"] == "longo":  # longo: em etapas (estrutura + um pedido por capítulo); o curto segue igual
        from .script_longo import escrever_longo
        r = escrever_longo(cand, fatos, cfg, hoje)
        modelo, erros = r.pop("_modelo", ""), []
    else:
        r, _, modelo = gerar_json(_prompt(cand, fatos, cfg, hoje, alvos), cfg, temperatura=0.7)
        erros = validar(r, fatos, cfg, hoje)
    for rodada in range(2 if cfg["formato"] != "longo" else 0):
        if not erros:
            break
        log(f"roteiro: {len(erros)} problema(s); pedindo correção ({rodada + 1}/2)")
        r2, _, modelo = gerar_json(_prompt(cand, fatos, cfg, hoje, alvos, erros, r), cfg, temperatura=0.4)
        e2 = validar(r2, fatos, cfg, hoje)
        if len(e2) <= len(erros):
            r, erros = r2, e2
    if cfg["formato"] != "longo" and (cfg.get("roteiro") or {}).get("critico", True):
        r, erros = revisar_narrativa(r, erros, cand, fatos, cfg, hoje, alvos)
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
    n_emo = emocoes_coerentes(r)
    if n_emo:
        log(f"roteiro: {n_emo} tag(s) de emoção ajustada(s) ao conteúdo da cena")
    r["formato"] = cfg["formato"]
    r["tema"] = r.get("tema") or fatos["tema"]
    r["slug"] = slugify(r["tema"])
    r["modelo_roteiro"] = modelo
    n_pal = sum(len(sc["text"].split()) for ch in r["chapters"] for sc in ch["scenes"])
    log(f"roteiro pronto ({modelo}): {len(r['chapters'])} capítulo(s), {sum(len(c['scenes']) for c in r['chapters'])} cenas, {n_pal} palavras")
    return r
