"""Etapas 7 e 8: publicacao.md (YouTube + TikTok) e relatório da execução."""
from __future__ import annotations

from pathlib import Path

from .util import NOTAS, nota


def _mmss(t: float) -> str:
    t = int(round(t))
    return f"{t // 60:02d}:{t % 60:02d}"


def capitulos(data: dict, roteiro: dict) -> list[tuple[str, str]]:
    out = [("00:00", roteiro["chapters"][0]["title"])]
    for s in data["segments"]:
        if s["kind"] == "chapter":
            out.append((_mmss(s["start"]), s["title"]))
    return out


def corte_tiktok(data: dict, roteiro: dict) -> dict | None:
    """Capítulo (sem a intro) com duração mais próxima de 75 s, limitado a 60–90 s."""
    segs = data["segments"]
    blocos = []
    atual = None
    for s in segs:
        if s["kind"] == "chapter":
            atual = {"titulo": s["title"], "ini": s["start"] + s["dur"], "fim": s["start"] + s["dur"], "primeira": None}
            blocos.append(atual)
        elif atual:
            atual["fim"] = s["start"] + s["dur"]
            atual["primeira"] = atual["primeira"] or s["text"]
    if not blocos:
        return None
    b = min(blocos, key=lambda x: abs((x["fim"] - x["ini"]) - 75))
    fim = min(b["fim"], b["ini"] + 90)
    if fim - b["ini"] < 60:
        fim = min(data["duration"], b["ini"] + 60)
    frase = (b["primeira"] or "").split(". ")[0].rstrip(".") + "."
    return {"titulo": b["titulo"], "ini": _mmss(b["ini"]), "fim": _mmss(fim), "frase": frase}


def _tags_ok(tags: list[str]) -> list[str]:
    out, tot = [], 0
    for t in tags:
        t = t.strip().strip("#")
        if not t or t.lower() in (x.lower() for x in out):
            continue
        if tot + len(t) + (2 if out else 0) > 500 or len(out) >= 25:
            break
        out.append(t)
        tot += len(t) + (2 if len(out) > 1 else 0)
    if len(out) < 15:
        nota(f"Tags: só {len(out)} tags válidas (o alvo é 15 a 25).")
    return out


def _pub_padrao(roteiro: dict) -> dict:
    tema = roteiro.get("tema", "Vídeo")
    return {"youtube": {"titulo": f"{tema}: entenda em minutos", "alternativos": [], "abertura": tema, "topicos": [], "cta": "Comenta aí o que você acha!",
                        "aviso": "", "hashtags": ["#ia", "#tecnologia"], "tags": [], "comentario_fixado": "Vai dar certo ou é miragem?",
                        "sintetico": {"resposta": "Não", "motivo": "animação claramente não realista; voz sintética genérica."},
                        "categoria": "Ciência e tecnologia", "horario": "18h–20h"},
            "tiktok": {"legenda": tema, "hashtags": ["#ia", "#tecnologia"], "capa": tema[:30], "primeira_frase": roteiro["chapters"][0]["scenes"][0]["text"],
                       "rotulo_ia": {"resposta": "Sim", "motivo": "narração com voz sintética."}, "som": "Manter a narração; música em alta só baixinha.",
                       "horario": "19h–21h"}}


def escrever(roteiro, data, pesquisa, fatos, voz, conf, medidas, issues, pasta: Path, cfg, data_hoje, modo) -> dict:
    curto = roteiro["formato"] == "curto"
    pub = roteiro.get("publicacao") or _pub_padrao(roteiro)
    yt, tk = pub["youtube"], pub["tiktok"]
    titulo = yt["titulo"].strip()
    if curto and "#shorts" not in titulo.lower():
        titulo = (titulo[:61].rstrip() + " #shorts")
    if len(titulo) > 70:
        nota(f"Título com {len(titulo)} caracteres (limite 70); cortei.")
        titulo = titulo[:70].rstrip()
    usados = []
    if fatos:
        ids = {i for ch in roteiro["chapters"] for sc in ch["scenes"] for i in sc.get("fact_ids", [])}
        usados = [f for f in fatos["fatos"] if f["id"] in ids] or fatos["fatos"]
    fontes = []
    for f in usados:
        k = (f["fonte"], f["url"])
        if k not in [(a, b) for a, b, _ in fontes]:
            fontes.append((f["fonte"], f["url"], f.get("data", "")))
    caps = capitulos(data, roteiro) if not curto else []
    tags = _tags_ok(yt.get("tags", []))

    desc = [yt.get("abertura", "").strip(), ""]
    desc += [t for t in yt.get("topicos", [])]
    desc += ["", yt.get("cta", "").strip(), ""]
    aviso = (yt.get("aviso") or "").strip()
    desc.append(((aviso + " ") if aviso else "") + "Animação feita 100% em código e narração com voz sintética.")
    if caps:
        desc += ["", "CAPÍTULOS"] + [f"{a} {b}" for a, b in caps]
    if fontes:
        desc += ["", "FONTES"] + [f"{n} ({d}): {u}" for n, u, d in fontes]
    desc += ["", " ".join(yt.get("hashtags", [])[:5])]
    descricao = "\n".join(desc).strip()
    corte = corte_tiktok(data, roteiro) if not curto else None

    L = [f"# Pacote de publicação — {roteiro.get('tema', '')} ({'CURTO 9:16' if curto else 'LONGO 16:9'}, {_mmss(data['duration'])})", ""]
    if pesquisa and pesquisa.get("vencedor", {}).get("url"):
        v = pesquisa["vencedor"]
        L += [f"Referência de tema e formato (não usamos nada do conteúdo): {v.get('titulo', '')} — {v['url']}", ""]
    L += ["## YOUTUBE", "", f"### Título principal ({len(titulo)} caracteres)", "```", titulo, "```", "",
          "### Títulos alternativos (teste A/B)", "```"] + [a + (" #shorts" if curto and "#shorts" not in a else "") for a in yt.get("alternativos", [])[:3]] + ["```", "",
          "### Descrição", "```", descricao, "```", "", f"### Tags ({len(tags)} tags, {len(', '.join(tags))} caracteres)", "```", ", ".join(tags), "```", "",
          "### Comentário fixado", "```", yt.get("comentario_fixado", ""), "```", "",
          "### Conteúdo alterado ou sintético", f"**{yt['sintetico']['resposta']}.** {yt['sintetico']['motivo']}", "",
          "### Categoria", yt.get("categoria", "Ciência e tecnologia"), "", "### Melhor horário (Brasil)", yt.get("horario", ""), "",
          "## TIKTOK", ""]
    if corte:
        L += ["### Corte sugerido (60–90 s)", f"**{corte['ini']} → {corte['fim']}**: capítulo \"{corte['titulo']}\". Comece direto na fala: \"{corte['frase']}\"", ""]
    L += ["### Legenda", "```", (tk.get("legenda", "").strip() + " " + " ".join(tk.get("hashtags", [])[:5])).strip(), "```", "",
          "### Texto da capa", "```", tk.get("capa", ""), "```", "", "### Primeira frase (prende em até 2 s)", f"\"{(corte or {}).get('frase') or tk.get('primeira_frase', '')}\"", "",
          "### Rótulo \"Conteúdo gerado por IA\"", f"**{tk['rotulo_ia']['resposta']}.** {tk['rotulo_ia']['motivo']}", "",
          "### Som", tk.get("som", ""), "", "### Horário sugerido", tk.get("horario", ""), "",
          "## Créditos", "Sem mídia de terceiros. Cenas, ícones, trilha e efeitos gerados em código. Fontes tipográficas Figtree e Anton (SIL Open Font License)."]
    pub_md = pasta / "publicacao.md"
    pub_md.write_text("\n".join(L) + "\n", encoding="utf-8")

    # relatório (release + resumo da execução)
    R = [f"# 🎬 {titulo}", "", f"**{'Curto 9:16' if curto else 'Longo 16:9'} · {_mmss(data['duration'])} · {conf['largura']}×{conf['altura']} · "
         f"{conf['tamanho_mb']} MB · voz: {voz.get('provedor')} {voz.get('modelo', '')} {voz.get('voz', '')}**", ""]
    if pesquisa:
        R += [pesquisa.get("md_vencedor", ""), ""]
        (pasta / "pesquisa.md").write_text(pesquisa.get("md", ""), encoding="utf-8")
    R += ["## YouTube", "```", titulo, "```", "```", descricao, "```", "```", ", ".join(tags), "```", "", "## TikTok", "```",
          (tk.get("legenda", "").strip() + " " + " ".join(tk.get("hashtags", [])[:5])).strip(), "```", f"Capa: **{tk.get('capa', '')}**"]
    if corte:
        R.append(f"Corte: **{corte['ini']} → {corte['fim']}** (\"{corte['titulo']}\")")
    if usados:
        R += ["", "## Fatos e fontes", "", "| Afirmação | Fonte | Data |", "|---|---|---|"]
        R += [f"| {f['afirmacao'].replace('|', '/')} | [{f['fonte']}]({f['url']}) | {f.get('data', '')} |" for f in usados]
        fatos_md = ["# Fatos verificados", "", "| # | Afirmação | Número conferido na página | Fonte | Data |", "|---|---|---|---|---|"]
        fatos_md += [f"| {f['id']} | {f['afirmacao']} | {', '.join(f.get('conferidos', [])) or 'texto'} | [{f['fonte']}]({f['url']}) | {f.get('data', '')} |" for f in fatos["fatos"]]
        if fatos.get("cortados"):
            fatos_md += ["", "## Cortados (não confirmados na página da fonte)", ""] + [f"- {c['afirmacao']} — {c['motivo']} ({c.get('url', '')})" for c in fatos["cortados"]]
        (pasta / "fatos.md").write_text("\n".join(fatos_md) + "\n", encoding="utf-8")
    R += ["", "## Conferências", f"- CRIVO 5 (layout): {'limpo' if not issues else str(len(issues)) + ' alerta(s)'} · ver `previa_crivo5.png`",
          f"- CRIVO 6: {conf['largura']}×{conf['altura']}, {conf['duracao']} s, áudio {'ok' if conf['audio'] else 'ausente'}; "
          f"mean_volume {medidas.get('mean_volume')} dB, {medidas.get('lufs')} LUFS, pico {medidas.get('true_peak')} dBTP · ver `folha_crivo6.png`",
          "", "## O que foi trocado ou não foi possível"]
    R += [f"- {n}" for n in dict.fromkeys(NOTAS)] or ["- Nada."]
    rel = pasta / "relatorio.md"
    rel.write_text("\n".join(R) + "\n", encoding="utf-8")
    return {"publicacao": pub_md, "relatorio": rel, "titulo": titulo}
