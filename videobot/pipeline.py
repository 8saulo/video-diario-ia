"""Orquestra as etapas 0–8 do prompt mestre, com os CRIVOs em código."""
from __future__ import annotations

import datetime as dt
import json
import shutil
from pathlib import Path
from zoneinfo import ZoneInfo

from . import audio, render, tts
from .util import NOTAS, RAIZ, escrever_json, etapa, falhar, ler_json, log, nota, resumo_github, slugify

HIST = RAIZ / "historico" / "temas.json"


def hoje() -> dt.date:
    return dt.datetime.now(ZoneInfo("America/Sao_Paulo")).date()


def historico() -> list:
    return ler_json(HIST, []) or []


def registrar_tema(entrada: dict):
    h = historico()
    h.append(entrada)
    escrever_json(HIST, h[-200:])


def escolher_paleta(cfg: dict, hist: list, data: dt.date) -> str:
    """Aplica a paleta de cores do vídeo em cfg['visual'] e devolve o nome dela.

    'rodizio' alterna a cada vídeo publicado: pega a paleta seguinte à do último vídeo do histórico
    (sem histórico, usa o dia do ano). Um nome fixo (ex.: 'roxo') usa sempre aquela.
    Vazio ou 'fixa' mantém acento/acento2 do config."""
    v = cfg["visual"]
    paletas = v.get("paletas") or {}
    pedido = str(v.get("paleta") or "").strip().lower()
    if not paletas or pedido in ("", "fixa"):
        return "fixa"
    nomes = list(paletas)
    if pedido == "rodizio":
        ultima = next((h.get("paleta") for h in reversed(hist) if h.get("paleta") in paletas), None)
        nome = nomes[(nomes.index(ultima) + 1) % len(nomes)] if ultima else nomes[data.toordinal() % len(nomes)]
    elif pedido in paletas:
        nome = pedido
    else:
        nota(f"Paleta '{pedido}' não existe em visual.paletas; usei '{nomes[0]}'.")
        nome = nomes[0]
    p = paletas[nome]
    v["acento"] = p.get("acento", v.get("acento"))
    v["acento2"] = p.get("acento2", v.get("acento2"))
    if p.get("acento_suave"):
        v["acento_suave"] = p["acento_suave"]
    log(f"paleta de cores: {nome} ({v['acento']} / {v['acento2']})")
    return nome


def _paleta_do_slug(cfg: dict, slug: str) -> None:
    """Para refazer: usa a mesma paleta que o vídeo original teve (pelo histórico)."""
    usada = next((h.get("paleta") for h in reversed(historico()) if h.get("slug") == slug and h.get("paleta")), None)
    if usada and usada in (cfg["visual"].get("paletas") or {}):
        cfg["visual"]["paleta"] = usada


def executar(cfg: dict, modo: str = "completo", refazer: str = "") -> dict:
    data_hoje = hoje()
    orig = None
    if refazer:
        orig = Path(refazer)
        if not (orig / "roteiro.json").exists():
            achados = sorted(orig.rglob("roteiro.json"))
            if not achados:
                falhar(f"Refazer: não achei roteiro.json em {orig}.")
            orig = achados[0].parent
        try:
            data_hoje = dt.date.fromisoformat(orig.name[:10])  # mesma data = mesma tag de Release
        except ValueError:
            pass
        roteiro0 = ler_json(orig / "roteiro.json", {})
        _paleta_do_slug(cfg, roteiro0.get("slug") or slugify(roteiro0.get("tema", "video")))
    paleta = escolher_paleta(cfg, historico(), data_hoje)
    curto = cfg["formato"] == "curto"
    pesquisa = fatos = None
    if orig:
        roteiro = roteiro0
        pesquisa = ler_json(orig / "pesquisa.json", None)
        fatos = ler_json(orig / "fatos.json", None)
        cfg["formato"] = roteiro.get("formato", cfg["formato"])
        curto = cfg["formato"] == "curto"
        tit = (((roteiro.get("publicacao") or {}).get("youtube") or {}).get("titulo"))
        if not curto and fatos and not tit:
            from .script_longo import embalar
            roteiro = embalar(roteiro, fatos, cfg)
        nota(f"Refazendo o vídeo de {data_hoje.isoformat()} ('{roteiro.get('tema', '')}') com o roteiro, os fatos e a "
             "pesquisa originais; só a narração, a animação e o render foram gerados de novo.")
    elif modo == "demo":
        roteiro = json.loads((RAIZ / "exemplos" / "demo.json").read_text(encoding="utf-8"))
        roteiro["formato"] = cfg["formato"]
        nota("Modo demo: roteiro fixo de exemplo (sem pesquisa e sem LLM), só para testar motor, voz e render.")
    else:
        from . import facts, llm, research, script
        from .util import chave
        provs = llm.disponiveis(cfg)
        if not provs:
            envs = ", ".join(f"**{llm.PROVEDORES[p]['env']}**" for p in llm.ordem(cfg))
            falhar(f"Falta a chave de pelo menos um provedor de texto ({envs}). Eles fazem a triagem, a checagem de fatos e o roteiro. "
                   "No GitHub: Settings → Secrets and variables → Actions → New repository secret. No PC: setx NOME \"chave\".")
        log("texto: " + " → ".join(llm.PROVEDORES[p]["titulo"] for p in provs)
            + f"; busca: {'Tavily + ' if chave('TAVILY_API_KEY') else ''}Wikipedia"
            + f"; voz: {'Gemini TTS' if chave('GEMINI_API_KEY') else 'edge-tts'}")
        if not chave("TAVILY_API_KEY"):
            nota("Sem TAVILY_API_KEY: a busca de fontes fica só com a Wikipedia. Notícias recentes ficam de fora.")
        etapa("pesquisa", "Pesquisa de tema no YouTube")
        pesquisa = research.pesquisar(cfg, historico(), data_hoje)
        etapa("fatos", "Checagem de fatos nas fontes")
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
        etapa("roteiro", "Roteiro")
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
    etapa("narracao", "Narração e alinhamento das palavras")
    narr = tts.narrar(roteiro, cfg, pasta)
    # fotos e vídeos reais (licença livre) ligados à fala de cada cena; depois, objetos 3D só onde não há mídia
    etapa("midia", "Fotos e vídeos de licença livre")
    from . import midia, objetos3d
    from .render import CAUDA
    longo = roteiro["formato"] == "longo"
    durs = {sid: c["dur"] + CAUDA for sid, c in narr["cenas"].items()}
    creditos = midia.aplicar(roteiro, cfg, pasta, durs, 1920 if longo else 1080, 1080 if longo else 1920,
                             int(cfg["visual"].get("fps", 30)))
    if longo and roteiro.get("thumb"):  # longo: thumb com foto real do assunto central
        capa = midia.foto_thumb(roteiro, cfg, pasta, creditos)
        if capa:
            roteiro["thumb"]["photo"] = capa["photo"]
            creditos = creditos + [{"cena": "thumb", "titulo": "foto da capa", "credito": capa["credito"], "pagina": capa["pagina"]}]
    if creditos:
        roteiro["creditos_fotos"] = creditos
    if (roteiro.get("cena3d") or cfg["visual"].get("cena3d") or "") not in ("", "gpon"):
        objetos3d.revisar(roteiro, cfg)
    # 5. animação
    etapa("cenas", "Montagem das cenas e prévia de layout")
    data = render.montar_timeline(roteiro, narr, cfg)
    escrever_json(pasta / "timeline.json", data)
    issues = render.previa(data, pasta)
    if issues:
        nota(f"CRIVO 5: {len(issues)} alerta(s) de layout na prévia (ver previa_crivo5.png): "
             + "; ".join(f"{i['seg']}:{i['tipo']}" for i in issues[:8]))
    etapa("audio", "Trilha, efeitos e mixagem")
    mix, medidas = audio.mixar(data["segments"], data["duration"], pasta, cfg)
    nome = f"{slug}_{'curto' if curto else 'longo'}.mp4"
    etapa("render", "Render quadro a quadro")
    video = render.render(data, mix, pasta, nome, int(cfg["visual"].get("workers", 0)))
    etapa("conferencia", "Conferência do arquivo e prévia leve")
    conf = render.conferir(video, data, pasta)
    prev = render.previa_leve(video, pasta, float(cfg["entrega"].get("limite_previa_mb", 30)))
    # 6. thumbs
    etapa("thumbs", "Thumbnails")
    th = render.thumbs(roteiro["thumb"], cfg, pasta, curto)
    # 7. pacote
    etapa("pacote", "Pacote de publicação")
    from . import publish
    pacote = publish.escrever(roteiro, data, pesquisa, fatos, narr["voz"], conf, medidas, issues, pasta, cfg, data_hoje, modo)
    for p in pasta.glob("_*"):
        if p.is_file() and p.suffix in (".wav", ".json", ".txt"):
            p.unlink()
    shutil.rmtree(pasta / "audio", ignore_errors=True)
    if modo != "demo" and not orig:
        registrar_tema({"data": data_hoje.isoformat(), "tema": roteiro["tema"], "slug": slug, "paleta": paleta,
                        "referencia": (pesquisa or {}).get("vencedor", {}).get("url", "")})
    saida = {"pasta": str(pasta), "video": str(video), "previa": str(prev) if prev else "", "thumbs": [str(t) for t in th],
             "publicacao": str(pacote["publicacao"]), "relatorio": str(pacote["relatorio"]), "tag": f"video-{data_hoje.isoformat()}-{slug}-{cfg['formato']}"[:100],
             "titulo": pacote["titulo"], "modo": modo}
    escrever_json(RAIZ / "saida" / "ultimo.json", saida)
    resumo_github(Path(pacote["relatorio"]).read_text(encoding="utf-8"))
    log("pronto:", video)
    return saida
