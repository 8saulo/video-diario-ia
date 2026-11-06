"""Orquestra as etapas 0–8 do prompt mestre, com os CRIVOs em código."""
from __future__ import annotations

import datetime as dt
import json
import shutil
from pathlib import Path
from zoneinfo import ZoneInfo

from . import audio, render, tts
from .util import NOTAS, RAIZ, escrever_json, falhar, ler_json, log, nota, resumo_github, slugify

HIST = RAIZ / "historico" / "temas.json"


def hoje() -> dt.date:
    return dt.datetime.now(ZoneInfo("America/Sao_Paulo")).date()


def historico() -> list:
    return ler_json(HIST, []) or []


def registrar_tema(entrada: dict):
    h = historico()
    h.append(entrada)
    escrever_json(HIST, h[-200:])


def executar(cfg: dict, modo: str = "completo") -> dict:
    data_hoje = hoje()
    curto = cfg["formato"] == "curto"
    pesquisa = fatos = None
    if modo == "demo":
        roteiro = json.loads((RAIZ / "exemplos" / "demo.json").read_text(encoding="utf-8"))
        roteiro["formato"] = cfg["formato"]
        nota("Modo demo: roteiro fixo de exemplo (sem pesquisa e sem LLM), só para testar motor, voz e render.")
    else:
        from . import facts, research, script
        from .util import chave
        if not chave("GEMINI_API_KEY"):
            falhar("Falta a secret **GEMINI_API_KEY** (chave do Google AI Studio). Ela escreve o roteiro, checa fatos e narra. "
                   "Adicione em Settings → Secrets and variables → Actions → New repository secret.")
        pesquisa = research.pesquisar(cfg, historico(), data_hoje)
        escolhido = None
        for cand in pesquisa["ranking"][:3]:
            log(f"tentando o tema: {cand['tema']}")
            fatos = facts.coletar(cand, cfg)
            if fatos["ok"]:
                escolhido = cand
                break
            nota(f"CRIVO 2/3: '{cand['tema']}' não teve fontes verificáveis suficientes ({fatos['motivo']}); passei para o próximo.")
        if not escolhido:
            falhar("Nenhum tema do dia passou na checagem de fatos (CRIVOs 2 e 3). Nada foi publicado.")
        pesquisa["vencedor"] = escolhido
        roteiro = script.escrever(escolhido, fatos, cfg, data_hoje)

    slug = roteiro.get("slug") or slugify(roteiro.get("tema", "video"))
    pasta = RAIZ / "saida" / f"{data_hoje.isoformat()}_{slug}"
    if pasta.exists():
        shutil.rmtree(pasta)
    pasta.mkdir(parents=True)
    escrever_json(pasta / "roteiro.json", roteiro)
    if pesquisa:
        escrever_json(pasta / "pesquisa.json", pesquisa)
    if fatos:
        escrever_json(pasta / "fatos.json", fatos)

    # 4. narração
    narr = tts.narrar(roteiro, cfg, pasta)
    # 5. animação
    data = render.montar_timeline(roteiro, narr, cfg)
    escrever_json(pasta / "timeline.json", data)
    issues = render.previa(data, pasta)
    if issues:
        nota(f"CRIVO 5: {len(issues)} alerta(s) de layout na prévia (ver previa_crivo5.png): "
             + "; ".join(f"{i['seg']}:{i['tipo']}" for i in issues[:8]))
    mix, medidas = audio.mixar(data["segments"], data["duration"], pasta, cfg)
    nome = f"{slug}_{'curto' if curto else 'longo'}.mp4"
    video = render.render(data, mix, pasta, nome, int(cfg["visual"].get("workers", 0)))
    conf = render.conferir(video, data, pasta)
    prev = render.previa_leve(video, pasta, float(cfg["entrega"].get("limite_previa_mb", 30)))
    # 6. thumbs
    th = render.thumbs(roteiro["thumb"], cfg, pasta, curto)
    # 7. pacote
    from . import publish
    pacote = publish.escrever(roteiro, data, pesquisa, fatos, narr["voz"], conf, medidas, issues, pasta, cfg, data_hoje, modo)
    for p in pasta.glob("_*"):
        if p.is_file() and p.suffix in (".wav", ".json", ".txt"):
            p.unlink()
    shutil.rmtree(pasta / "audio", ignore_errors=True)
    if modo != "demo":
        registrar_tema({"data": data_hoje.isoformat(), "tema": roteiro["tema"], "slug": slug,
                        "referencia": (pesquisa or {}).get("vencedor", {}).get("url", "")})
    saida = {"pasta": str(pasta), "video": str(video), "previa": str(prev) if prev else "", "thumbs": [str(t) for t in th],
             "publicacao": str(pacote["publicacao"]), "relatorio": str(pacote["relatorio"]), "tag": f"video-{data_hoje.isoformat()}-{slug}-{cfg['formato']}"[:100],
             "titulo": pacote["titulo"], "modo": modo}
    escrever_json(RAIZ / "saida" / "ultimo.json", saida)
    resumo_github(Path(pacote["relatorio"]).read_text(encoding="utf-8"))
    log("pronto:", video)
    return saida
