"""Roteiro do vídeo LONGO (16:9), em etapas, com estrutura de retenção para YouTube.

Por que em etapas: um roteiro de ~8 min com cenas em JSON passa de 10 mil tokens, acima do limite por
minuto dos modelos grátis (Groq). Então:
  1. ESTRUTURA: título + promessa + capítulos (cada um com objetivo, fatos e o gancho que puxa o próximo),
     thumb e publicação;
  2. CAPÍTULOS: um pedido por capítulo, com o orçamento de palavras e a última fala do capítulo anterior
     (continuidade), validado e corrigido capítulo a capítulo.
O vídeo curto continua com o roteiro de sempre (script.escrever).
"""
from __future__ import annotations

import json

from .llm import gerar_json
from .objetos3d import prompt_catalogo
from .util import log, nota, slugify

REGRAS_VIRAL = """ESTRUTURA DE RETENÇÃO (YouTube, vídeo longo):
- Os primeiros 30 segundos decidem tudo. Abra com o fato mais forte (número chocante, virada, consequência para o espectador),
  diga o que está em jogo e PROMETA o que ele vai saber até o fim. Nada de "olá", "neste vídeo", "fala pessoal", apresentação de canal.
- Cada capítulo abre com uma pergunta ou tensão e termina com um GANCHO ABERTO que puxa o próximo ("mas isso não explica por que...").
- Uma revelação por cena. A cada ~1 minuto, quebra de padrão: pergunta direta ao espectador, contraste, "agora vem a parte estranha".
- Entregue a promessa no fim (payoff) com uma última virada. Inclua o outro lado (contraponto) de forma honesta.
- Tom de conversa com o espectador ("você"), frases curtas, verbos fortes, curiosidade e leve ironia; nada de linguagem de relatório."""

REGRAS_TEXTO = """REGRAS DE TEXTO
- Narração em PT-BR falado. Escreva TODOS os números por extenso como se fala ("dois vírgula um trilhões", "dois mil e vinte e oito");
  nada de algarismos na narração. Escreva "IA", nunca "I.A.". Use "!" e "?" para guiar a entonação e reticências ("...") para pausa
  dramática antes de uma revelação (no máximo 1 por cena).
- Toda afirmação com número precisa vir de um fato da lista (fact_ids). Sem fato, sem número. Não invente nada.
- Os "params" das cenas são o que aparece na tela: números com algarismos (ex.: value 2.1, suffix " tri"), sempre iguais aos dos fatos
  citados. Textos de tela curtos.
- Não diga que conteúdo sintético é real. Interfaces de chat são ilustrativas."""


def _fatos_txt(fatos: dict) -> str:
    return "\n".join(f'[{f["id"]}] {f["afirmacao"]} | números na fonte: {", ".join(f.get("numeros") or []) or "—"} | '
                     f'{f["fonte"]}, {f.get("data", "")} | lado: {f.get("lado", "")}' for f in fatos["fatos"])


def prompt_estrutura(cand: dict, fatos: dict, cfg: dict, hoje, alvos: dict) -> str:
    caps = alvos["caps"]
    return f"""Você é o roteirista-chefe de um canal brasileiro de {cfg['tema'].get('nicho', 'IA e tecnologia')} no YouTube que faz vídeos
longos com alta retenção (motion graphics, fotos e vídeos reais, voz narrada). Data de hoje: {hoje.strftime('%d/%m/%Y')}.
Tema: "{fatos['tema']}". Ângulo: {fatos.get('angulo', '')}.
{('Referência (copie só TEMA e FORMATO, nunca o conteúdo): "' + cand['titulo'] + '"') if cand.get('titulo') else ''}

FATOS VERIFICADOS (a base de tudo; cite os ids):
{_fatos_txt(fatos)}

{REGRAS_VIRAL}

Monte a ESTRUTURA de um vídeo de ~{alvos['seg'] / 60:.0f} minutos com {caps[0]} a {caps[1]} capítulos:
- capítulo 1 = o gancho (30 a 45 s) + a promessa; o último = payoff + virada final + pergunta para os comentários.
- títulos de capítulo com até 4 palavras, intrigantes (viram cartela na tela e capítulos na descrição).
- distribua os fatos: cada fato no capítulo onde ele tem mais impacto; guarde um fato forte para o final.

TÍTULO E THUMB (o que faz clicar):
- youtube.titulo: até 60 caracteres, palavra-chave no começo, curiosidade (lacuna de informação) com número ou contraste,
  promessa que o vídeo CUMPRE (nada de mentira). 3 alternativos bem diferentes entre si para teste A/B.
- thumb: 2 a 4 palavras GRANDES que COMPLEMENTAM o título (não repetem), emoção/tensão; um número forte dos fatos.
- thumb_foto: busca curta EM INGLÊS (2 a 4 palavras) da foto real que deve estar na thumb: o rosto/pessoa, a empresa, o produto
  ou o lugar central do tema (ex.: "Sam Altman", "Nvidia headquarters", "Tesla Optimus robot").

PUBLICAÇÃO
- youtube.abertura: 2 linhas com gancho e palavra-chave. topicos: 4 a 6 linhas começando com emoji. cta: pergunta de comentário.
  aviso: '' ou aviso de finanças/IA. hashtags: 3 a 5. tags: 18 a 24 (PT-BR amplas e de cauda longa + 2 ou 3 em inglês), até 480 caracteres.
  comentario_fixado: pergunta binária. sintetico: {{"resposta":"Não","motivo":"animação e voz sintética claramente não realistas"}}.
  categoria. horario (sugestão para o Brasil).
- tiktok: legenda (até 150 caracteres), hashtags (3 a 5), capa (até 4 palavras), primeira_frase,
  rotulo_ia {{"resposta":"Sim","motivo":"narração com voz sintética"}}, som, horario.

Responda SOMENTE com JSON:
{{"tema": "...", "promessa": "o que o espectador vai saber até o fim",
 "capitulos": [{{"title": "...", "objetivo": "o que este capítulo entrega", "fact_ids": [1, 2], "gancho_final": "frase de loop aberto"}}],
 "thumb": {{"lines": [{{"text": "ATÉ 2 PALAVRAS"}}, {{"text": "ATÉ 2 PALAVRAS", "hl": true}}], "number": "número dos fatos, com algarismos",
           "numberLabel": "até 4 palavras", "icon": "ICONE"}},
 "thumb_foto": "...",
 "publicacao": {{"youtube": {{...}}, "tiktok": {{...}}}}}}"""


def prompt_capitulo(cand, fatos, cfg, hoje, est: dict, i: int, palavras: int, anterior_txt: str, erros=None, rascunho=None) -> str:
    from .script import TEMPLATES
    caps = est["capitulos"]
    ch = caps[i]
    n_cenas = max(4, round(palavras / 26))
    papel = ("GANCHO: a primeira cena tem no máximo 16 palavras e é o fato mais forte do vídeo; nas seguintes, o que está em jogo e a "
             f"PROMESSA (\"{est.get('promessa', '')}\"). Sem saudação, sem apresentar o canal." if i == 0 else
             "FINAL: entregue a promessa, traga a última virada e feche com uma cena template cta (kind \"comment\", options binárias) "
             "pedindo comentário e convidando para o próximo vídeo." if i == len(caps) - 1 else
             "MEIO: abra com uma pergunta/tensão, uma revelação por cena, uma pergunta direta ao espectador no meio, feche com o gancho.")
    if i == max(1, len(caps) // 2 - 1):
        papel += (" Este capítulo tem, depois de uma revelação forte, UMA cena template cta (kind \"subscribe\") curta e natural "
                  "pedindo inscrição (sem números).")
    plano = "\n".join(f'{k + 1}. {c["title"]}: {c.get("objetivo", "")} (fatos {c.get("fact_ids", [])})' for k, c in enumerate(caps))
    p = f"""Você escreve o capítulo {i + 1} de {len(caps)} de um vídeo longo do YouTube sobre "{fatos['tema']}" (canal brasileiro de
{cfg['tema'].get('nicho', 'IA e tecnologia')}, motion graphics com fotos/vídeos reais e voz narrada). Data de hoje: {hoje.strftime('%d/%m/%Y')}.

PLANO DO VÍDEO:
{plano}
Promessa ao espectador: {est.get('promessa', '')}

ESTE CAPÍTULO: "{ch['title']}" — {ch.get('objetivo', '')}
Papel: {papel}
{('Termine com este gancho para o próximo capítulo: "' + ch.get('gancho_final', '') + '"') if i < len(caps) - 1 else ''}
{('Última fala do capítulo anterior (continue a partir dela, sem repetir): "' + anterior_txt + '"') if anterior_txt else ''}

TAMANHO: {n_cenas} cenas (± 2), cerca de {palavras} palavras de narração no capítulo (cada cena com 18 a 35 palavras, 2 ou 3 frases curtas).
Conte as palavras: frases curtas NÃO significam capítulo curto. Varie o template entre cenas (nunca 3 iguais seguidas).

FATOS VERIFICADOS (use SOMENTE estes números; prefira os do capítulo {ch.get('fact_ids', [])}):
{_fatos_txt(fatos)}

{REGRAS_VIRAL}

{REGRAS_TEXTO}
{'- O tema é de finanças: inclua o aviso "não é recomendação de investimento" no capítulo final.' if fatos.get('financas') else ''}

{TEMPLATES}

{prompt_catalogo()}

DIREÇÃO DE VOZ (campo "emocao" em cada cena, 2 a 5 palavras): a emoção que a frase pede, VARIANDO entre cenas
(ex.: "empolgado, com espanto", "intrigado, baixando o tom", "sério e firme", "irônico, sorrindo", "urgente, acelerando", "caloroso").

Responda SOMENTE com JSON:
{{"scenes": [{{"id": "slug_unico", "text": "narração", "template": "...", "params": {{...}}, "objetos3d": ["id do catálogo 3D"],
  "emocao": "...", "fact_ids": [1]}}]}}"""
    if erros:
        p += "\n\nSEU RASCUNHO TEVE ESTES PROBLEMAS. Corrija todos e devolva o JSON completo do capítulo:\n- " + "\n- ".join(erros[:25])
        p += "\n\nRASCUNHO:\n" + json.dumps(rascunho, ensure_ascii=False)[:30000]
    return p


def _erros_capitulo(cenas: list, fatos: dict, cfg: dict, hoje, palavras: int) -> list[str]:
    """Valida só o capítulo: números na tela/algarismos/templates (validar() com formato neutro) + tamanho."""
    from .script import validar
    err = validar({"chapters": [{"title": "x", "scenes": cenas}], "thumb": {"lines": [{"text": "x"}]},
                   "publicacao": {"youtube": {"titulo": "x"}, "tiktok": {"x": 1}}}, fatos, dict(cfg, formato="__capitulo"), hoje)
    err = [e for e in err if not e.startswith("o roteiro tem") and "capítulos" not in e]
    n = sum(len(sc.get("text", "").split()) for sc in cenas)
    if not 0.75 * palavras <= n <= 1.3 * palavras:
        err.append(f"o capítulo tem {n} palavras; precisa ter cerca de {palavras} (entre {int(0.75 * palavras)} e {int(1.3 * palavras)})")
    return err


def prompt_embalagem(r: dict, fatos: dict) -> str:
    caps = "\n".join(f'{i + 1}. {c["title"]}: {c["scenes"][0]["text"][:140]}' for i, c in enumerate(r.get("chapters", [])) if c.get("scenes"))
    nums = "; ".join(f'[{f["id"]}] {f["afirmacao"][:110]}' for f in fatos.get("fatos", [])[:14])
    return f"""Você é especialista em embalagem de vídeos do YouTube (título + thumbnail), focado em CTR alto sem enganar.
Vídeo longo pronto sobre "{r.get('tema', '')}". Promessa: {r.get('promessa', '')}
Capítulos e como cada um começa:
{caps}
Fatos (use só estes números): {nums}

Crie:
- titulo: até 60 caracteres, palavra-chave no começo, lacuna de curiosidade com número ou contraste; promessa que o vídeo cumpre.
- alternativos: 3 títulos bem diferentes entre si (ângulos: número chocante, pergunta, consequência para o espectador).
- thumb: 2 a 4 palavras GRANDES que COMPLEMENTAM o título (não repetem), emoção/tensão sem sensacionalismo falso;
  um número forte dos fatos (com algarismos) e um rótulo de até 4 palavras que diga a unidade/contexto do número.
- thumb_foto: busca EM INGLÊS (2 a 4 palavras) de uma foto real VISUALMENTE FORTE e reconhecível para a thumb: o rosto da pessoa
  central, o produto, a fachada/logo da empresa, ou a cena concreta mais impactante (ex.: "Sam Altman", "Nvidia H100 GPU",
  "power plant cooling towers"). Evite ambientes genéricos e escuros (ex.: "data center interior").

Revise o português (concordância: "SUA conta", não "SEU conta"; acentos) antes de responder.
Responda SOMENTE com JSON:
{{"titulo": "...", "alternativos": ["...", "...", "..."],
 "thumb": {{"lines": [{{"text": "ATÉ 2 PALAVRAS"}}, {{"text": "ATÉ 2 PALAVRAS", "hl": true}}], "number": "...", "numberLabel": "...", "icon": "ia"}},
 "thumb_foto": "..."}}"""


def _achatar_embalagem(e) -> dict:
    """Aceita as variações que os modelos devolvem: "título"/"title", tudo dentro de "youtube", título como lista."""
    if not isinstance(e, dict):
        return {}
    e = dict(e)
    for k in ("youtube", "publicacao"):
        if isinstance(e.get(k), dict):
            for k2, v in e[k].items():
                e.setdefault(k2, v)
    for de, para in (("título", "titulo"), ("title", "titulo"), ("titulos_alternativos", "alternativos"), ("alternatives", "alternativos")):
        if de in e and para not in e:
            e[para] = e[de]
    if isinstance(e.get("titulo"), list):
        lst = [str(x) for x in e["titulo"] if str(x).strip()]
        e["titulo"] = lst[0] if lst else ""
        e.setdefault("alternativos", lst[1:])
    return e


def embalar(r: dict, fatos: dict, cfg: dict) -> dict:
    """Título, alternativos e thumb do longo, feitos com o roteiro já escrito (run #23 saiu sem título)."""
    e, m = {}, ""
    for _ in range(2):  # run #25: veio sem título; tenta de novo antes de desistir
        try:
            e, _, m = gerar_json(prompt_embalagem(r, fatos), cfg, temperatura=0.8, max_tokens=1500)
        except Exception as ex:
            nota(f"Embalagem do longo falhou ({str(ex)[:90]}); mantive título e thumb da estrutura.")
            return r
        e = _achatar_embalagem(e)
        if str(e.get("titulo") or "").strip():
            break
    pub = r.setdefault("publicacao", {}) if isinstance(r.get("publicacao"), dict) else r.setdefault("publicacao", {})
    yt = pub.setdefault("youtube", {}) if isinstance(pub.get("youtube"), dict) else pub.setdefault("youtube", {})
    tit = str(e.get("titulo") or "").strip()
    if tit and len(tit) <= 70:
        yt["titulo"] = tit
        yt["alternativos"] = [str(a).strip() for a in (e.get("alternativos") or []) if str(a).strip() and len(str(a)) <= 70][:3]
    th = e.get("thumb")
    if isinstance(th, dict) and th.get("lines"):
        r["thumb"] = th
    if str(e.get("thumb_foto") or "").strip():
        r["thumb_foto"] = str(e["thumb_foto"]).strip()
    log(f"  embalagem ({m}): título '{yt.get('titulo', '')}' | thumb: {' '.join(l.get('text', '') for l in (r.get('thumb') or {}).get('lines', []))}")
    return r


def escrever_longo(cand: dict, fatos: dict, cfg: dict, hoje) -> dict:
    from .script import _alvos, _sanear, validar
    alvos = _alvos(cfg)
    est, _, modelo = gerar_json(prompt_estrutura(cand, fatos, cfg, hoje, alvos), cfg, temperatura=0.7, max_tokens=6000)
    caps = [c for c in (est.get("capitulos") or []) if isinstance(c, dict) and c.get("title")]
    if len(caps) < alvos["caps"][0]:
        raise RuntimeError(f"a estrutura veio com {len(caps)} capítulos (mínimo {alvos['caps'][0]})")
    caps = caps[:alvos["caps"][1]]
    est["capitulos"] = caps
    log(f"roteiro longo: estrutura com {len(caps)} capítulos ({modelo}); promessa: {str(est.get('promessa', ''))[:90]}")
    total = sum(alvos["palavras"]) / 2
    # gancho e final um pouco menores; o meio carrega o conteúdo
    pesos = [0.7] + [1.0] * (len(caps) - 2) + [0.85]
    orc = [round(total * w / sum(pesos)) for w in pesos]
    chapters, anterior = [], ""
    for i, ch in enumerate(caps):
        r, _, m = gerar_json(prompt_capitulo(cand, fatos, cfg, hoje, est, i, orc[i], anterior), cfg, temperatura=0.75, max_tokens=7000)
        cenas = [sc for sc in (r.get("scenes") or []) if isinstance(sc, dict) and sc.get("text")]
        erros = _erros_capitulo(cenas, fatos, cfg, hoje, orc[i])
        if erros:
            log(f"  capítulo {i + 1}: {len(erros)} problema(s); pedindo correção")
            r2, _, m = gerar_json(prompt_capitulo(cand, fatos, cfg, hoje, est, i, orc[i], anterior, erros, cenas), cfg,
                                  temperatura=0.4, max_tokens=7000)
            c2 = [sc for sc in (r2.get("scenes") or []) if isinstance(sc, dict) and sc.get("text")]
            e2 = _erros_capitulo(c2, fatos, cfg, hoje, orc[i])
            if c2 and len(e2) <= len(erros):
                cenas, erros = c2, e2
        if not cenas:
            raise RuntimeError(f"o capítulo {i + 1} veio sem cenas")
        if erros:
            nota(f"Roteiro, capítulo {i + 1}: pendências: " + "; ".join(erros[:4]))
        n = sum(len(sc["text"].split()) for sc in cenas)
        log(f"  capítulo {i + 1}/{len(caps)} '{ch['title']}': {len(cenas)} cenas, {n} palavras ({m})")
        chapters.append({"title": ch["title"], "scenes": cenas})
        anterior = cenas[-1]["text"]
    # ids únicos no vídeo todo (cada capítulo foi escrito separado)
    vistos = set()
    for ch in chapters:
        for sc in ch["scenes"]:
            base = slugify(sc.get("id") or "cena", 26)
            sid, k = base, 2
            while sid in vistos:
                sid, k = f"{base}_{k}", k + 1
            vistos.add(sid); sc["id"] = sid
    r = {"tema": est.get("tema") or fatos["tema"], "chapters": chapters, "thumb": est.get("thumb") or {},
         "thumb_foto": str(est.get("thumb_foto") or "").strip(), "promessa": est.get("promessa", ""),
         "publicacao": est.get("publicacao") or {}}
    r = embalar(r, fatos, cfg)
    erros = validar(r, fatos, cfg, hoje)
    if erros:
        nota("Roteiro longo: pendências: " + "; ".join(erros[:6]))
        r = _sanear(r, fatos, cfg, hoje)
    r["_modelo"] = modelo
    return r
