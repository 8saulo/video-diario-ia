"""Série de vídeos curtos (config.yml → serie): um episódio a cada N dias, com tema, cores e capa padronizados.

  serie:
    ativo: true
    id: redes
    nome: "Redes na Prática"         # vai no título ("Redes na Prática #03 | ...") e na capa
    inicio: "2026-11-24"             # 1º dia da série; episódio nos dias inicio, inicio+N, inicio+2N...
    intervalo_dias: 2                # 2 = um dia sim, outro não
    publico: "técnicos de telecom..."
    config: {...}                    # trecho do config.yml só para os episódios (paleta, estilo, nº de cenas...)
    episodios:
      - titulo: "TX e RX na rede GPON"   # título do episódio (capa e YouTube)
        capa: ["TX E RX", "NO GPON"]     # 2 linhas da capa (a 2ª com destaque)
        icone: fiber
        tema: "..."                      # o que o episódio ensina (vai para a checagem de fatos e o roteiro)
        buscas: ["..."]                  # buscas web garantidas na checagem
        proximo: "..."                   # o que o PRÓXIMO episódio ensina, para o gancho "No próximo vídeo, vamos aprender ..."

Nos dias da série o curto do dia É o episódio (não sai outro curto). O longo semanal de domingo continua.
O número do episódio sai do histórico (historico/temas.json, campos "serie" e "episodio"): um episódio que
falhou não é pulado; ele sai no próximo dia da série.
"""
from __future__ import annotations

import copy
import datetime as dt
import re

from .util import log, nota


def _cfg_serie(cfg: dict) -> dict | None:
    s = cfg.get("serie")
    if not isinstance(s, dict) or not s.get("ativo") or not s.get("episodios"):
        return None
    return s


def dia_da_serie(cfg: dict, data: dt.date) -> bool:
    s = _cfg_serie(cfg)
    if not s:
        return False
    try:
        ini = dt.date.fromisoformat(str(s.get("inicio")))
    except ValueError:
        return False
    passo = max(1, int(s.get("intervalo_dias", 2)))
    return data >= ini and (data - ini).days % passo == 0


def numero_episodio(cfg: dict, hist: list, data: dt.date) -> int:
    """Próximo episódio = episódios já publicados antes de hoje + 1 (refazer no mesmo dia mantém o número)."""
    s = _cfg_serie(cfg) or {}
    hoje_iso = data.isoformat()
    de_hoje = [h for h in hist if h.get("serie") == s.get("id") and h.get("data") == hoje_iso and h.get("episodio")]
    if de_hoje:
        return int(de_hoje[-1]["episodio"])
    feitos = {int(h["episodio"]) for h in hist if h.get("serie") == s.get("id") and h.get("episodio") and h.get("data", "") < hoje_iso}
    return (max(feitos) if feitos else 0) + 1


def _merge(a: dict, b: dict) -> dict:
    out = copy.deepcopy(a)
    for k, v in (b or {}).items():
        out[k] = _merge(out[k], v) if isinstance(v, dict) and isinstance(out.get(k), dict) else copy.deepcopy(v)
    return out


def _chamada(ep: dict, prox: dict) -> str:
    """Gancho do episódio para o seguinte ("No próximo vídeo, vamos aprender <isto>"): o campo "proximo" do episódio
    atual; sem ele, o título do próximo."""
    t = str(ep.get("proximo") or prox.get("titulo") or "").strip()
    return t[:1].lower() + t[1:] if t[:2] != t[:2].upper() else t  # "TX e RX..." fica; "Como..." vira "como..."


def aplicar(cfg: dict, data: dt.date, hist: list) -> dict | None:
    """Dia de série e vídeo curto: põe o episódio em cfg (tema fixo, cores, estilo, instruções). Devolve cfg['_serie'] ou None."""
    s = _cfg_serie(cfg)
    if not s or cfg.get("formato") != "curto" or not dia_da_serie(cfg, data):
        return None
    eps = s["episodios"]
    n = numero_episodio(cfg, hist, data)
    if n > len(eps):
        nota(f"Série '{s.get('nome')}': os {len(eps)} episódios do config já saíram; hoje sai o curto normal. "
             "Acrescente episódios em config.yml → serie.episodios para continuar.")
        return None
    modelo = str(s.get("roteiro_fixo") or "").strip()
    arq = modelo.format(n=n) if modelo else ""
    if arq:  # 26/11: cada episódio tem roteiro e cena próprios; sem eles, o episódio não sai (nada de cenário reaproveitado)
        from .util import RAIZ
        if not (RAIZ / arq).exists():
            nota(f"Série '{s.get('nome')}': o episódio {n} ainda não tem roteiro e cena próprios ({arq}); hoje sai o curto normal "
                 f"e a série continua do episódio {n} no próximo dia da série.")
            return None
    ep, prox = eps[n - 1], (eps[n] if n < len(eps) else None)
    novo = _merge(cfg, s.get("config") or {})
    cfg.clear(); cfg.update(novo)
    nome = str(s.get("nome") or "Série").strip()
    t = cfg.setdefault("tema", {})
    t["tema_fixo"] = str(ep.get("tema") or ep["titulo"]).strip()
    t["buscas_fatos"] = [str(b) for b in (ep.get("buscas") or []) if str(b).strip()]
    t["angulo"] = (f"Episódio {n} de {len(eps)} da série '{nome}' para {s.get('publico', 'técnicos de redes')}: "
                   f"{ep['titulo']}. Didático e prático, do jeito que o técnico usa em campo.")
    t["nicho"] = f"{nome} · EP {n:02d}"
    if arq:
        t["roteiro_fixo"] = arq  # storyboard, narração e cena próprios do episódio
    t.pop("categoria", None)
    info = {"id": s.get("id", "serie"), "nome": nome, "n": n, "total": len(eps), "titulo": str(ep["titulo"]).strip(),
            "capa": list(ep.get("capa") or [])[:2], "icone": ep.get("icone") or "signal",
            "proximo": _chamada(ep, prox) if prox else "", "proximo_titulo": str(prox["titulo"]).strip() if prox else ""}
    cfg["_serie"] = info
    r = cfg.setdefault("roteiro", {})
    gancho = (f'A ÚLTIMA cena antes do CTA diz: "No próximo vídeo, vamos aprender {info["proximo"]}."' if prox else
              "Este é o último episódio da série: feche agradecendo quem acompanhou a série.")
    extra = f"""SÉRIE "{nome}", episódio {n} de {len(eps)}: {ep['titulo']}.
Público: {s.get('publico', 'técnicos de redes')}. Tom de instrutor experiente explicando para o colega de equipe: didático, prático, sem enrolação.
- Comece direto no problema ou na pergunta do técnico (cena 1). Ensine UMA coisa bem ensinada, com o passo a passo que ele aplica em campo.
- UMA CENA SÓ: o vídeo inteiro acontece no cenário 3D do caminho da internet; a câmera voa de um lugar para o outro. Toda cena diz
  params.local (o lugar do cenário de que a frase fala) e, por cima, o desenho técnico 2D daquela frase.
- CENAS TÉCNICAS: uma ideia por cena, e a tela mostra EXATAMENTE o que a frase diz. Comando citado -> template terminal com o
  comando e a saída real; equipamento, caminho do sinal ou enlace -> topologia (com path, highlight no enlace certo, down no que
  caiu); nível de sinal/atenuação/latência -> faixa com as zonas corretas; número -> bignumber/kpis; antes/depois -> compare.
- Cada cena traz uma informação NOVA: não repita o mesmo número nem a mesma frase em várias cenas.
- VALORES DE REFERÊNCIA (use exatamente estes; nunca invente faixas): {s.get('referencias', '')}
- Termos técnicos corretos (dBm, nm, OLT, ONU, VLAN...) e valores típicos de mercado; nada de marca de equipamento sem necessidade.
- {gancho}
- Não diga o número do episódio na narração (ele já aparece na tela)."""
    r["notas"] = (str(r.get("notas") or "").strip() + "\n" + extra).strip()
    log(f"série: {nome} #{n:02d} — {info['titulo']}")
    nota(f"Série '{nome}': episódio {n} de {len(eps)} ({info['titulo']}).")
    return info


def titulo(info: dict, sugerido: str = "") -> str:
    """Título padrão da série: '<Nome> #03 | <título do episódio>' (o #shorts entra depois, na publicação)."""
    return f"{info['nome']} #{info['n']:02d} | {info['titulo']}"


_PROX = re.compile(r"pr[oó]xim[oa]\s+(v[ií]deo|epis[oó]dio)", re.I)


def finalizar(roteiro: dict, info: dict) -> None:
    """Depois do roteiro: título e capa numerados, gancho do próximo episódio garantido e marcas para o histórico."""
    roteiro["serie"] = {k: info[k] for k in ("id", "nome", "n", "total", "titulo")}
    pub = roteiro.setdefault("publicacao", {})
    yt = pub.setdefault("youtube", {}) if isinstance(pub, dict) else {}
    yt["titulo"] = titulo(info)
    yt["alternativos"] = []
    tk = pub.setdefault("tiktok", {})
    if isinstance(tk, dict):
        tk["capa"] = f"#{info['n']:02d} {info['titulo']}"[:40]
    linhas = info.get("capa") or []
    th = roteiro.setdefault("thumb", {})
    th["lines"] = ([{"text": str(linhas[0])}, {"text": str(linhas[1]), "hl": True}] if len(linhas) >= 2
                   else (th.get("lines") or [{"text": info["titulo"].upper(), "hl": True}]))
    th["icon"] = info.get("icone") or th.get("icon") or "signal"
    th["serie"] = {"nome": info["nome"], "ep": info["n"], "total": info["total"]}
    th.pop("number", None); th.pop("numberLabel", None)
    if not info.get("proximo"):
        return
    cenas = [sc for ch in roteiro.get("chapters", []) for sc in ch.get("scenes", [])]
    if any(_PROX.search(str(sc.get("text", ""))) for sc in cenas):
        return
    # o roteirista esqueceu o gancho: entra uma cena antes do CTA (o roteiro ainda não foi narrado)
    cena = {"id": "proximo_ep", "text": f"No próximo vídeo, vamos aprender {info['proximo']}.", "emocao": "curioso, intrigante",
            "template": "headline", "fact_ids": [],
            "params": {"eyebrow": f"Próximo · EP {info['n'] + 1:02d}", "text": info["proximo_titulo"] or info["proximo"],
                       "highlight": [], "icon": "play"}}
    ch = (roteiro.get("chapters") or [{}])[-1]
    sc = ch.setdefault("scenes", [])
    pos = next((i for i, x in enumerate(sc) if x.get("template") == "cta"), len(sc))
    sc.insert(pos, cena)
    nota("Série: o roteiro veio sem o gancho do próximo episódio; acrescentei a cena antes do CTA.")
