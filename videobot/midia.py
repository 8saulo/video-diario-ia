"""Fotos e vídeos reais por cena (Wikimedia Commons e Openverse, sem chave; Pixabay, com chave grátis opcional).

Fluxo:
1. A IA lê a narração de cada cena e escreve buscas em inglês do que deve aparecer LITERALMENTE
   (a pessoa, a empresa, o produto, o lugar), dizendo se prefere vídeo ou foto.
2. Busca candidatos: vídeos e fotos no Commons; fotos no Openverse. Só licenças que permitem uso
   comercial e edição (CC0, domínio público, CC BY, CC BY-SA), com crédito do autor.
3. A IA vê título, descrição e categorias dos candidatos e escolhe o que mostra exatamente o que a
   frase fala, ou nenhum. Sem candidato relacionado, a cena fica sem mídia (nunca uma imagem genérica).
4. Baixa: foto em ~1600 px; vídeo vira sequência de quadros (o motor desenha quadro a quadro).
"""
from __future__ import annotations

import html
import json
import re
import subprocess
from pathlib import Path

import requests

from .util import log, nota

UA = "video-diario-ia/1.0 (https://github.com/8saulo/video-diario-ia)"
COMMONS = "https://commons.wikimedia.org/w/api.php"
OPENVERSE = "https://api.openverse.org/v1/images/"
# títulos que denunciam o que não é foto/vídeo real do assunto
NAO_FOTO = re.compile(r"illustrat|diagram|chart|graph|infographic|statistic|(?<![a-z])maps?(?![a-z])|logo|icon|screenshot|drawing|clipart|vector|poster|"
                      r"render|cartoon|meme|svg|scheme|flowchart|(?<![a-z])table(?![a-z])|(?<![a-z])plot(?![a-z])", re.I)


def serve(c: dict) -> bool:
    """Filtro antes da IA: foto em JPEG (PNG/SVG na Commons costumam ser gráficos) e título sem cara de diagrama."""
    if NAO_FOTO.search(c.get("titulo") or ""):
        return False
    if c["tipo"] == "foto" and not re.search(r"\.jpe?g(\?|$)", (c.get("url") or "").lower()):
        return False
    return True


def licenca_ok(lic: str) -> bool:
    """Aceita CC0, domínio público, CC BY e CC BY-SA. Recusa NC (não comercial) e ND (sem edição)."""
    l = (lic or "").lower().replace("_", "-").strip()
    if not l or "nc" in re.split(r"[-\s.]", l) or "nd" in re.split(r"[-\s.]", l):
        return False
    return l.startswith(("cc0", "pdm", "pd", "public domain", "cc-by", "cc by", "by"))


def _limpo(txt: str, n: int = 160) -> str:
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", txt or ""))).strip()[:n]


def _get(url, params, timeout=20, tentativas=2):
    for k in range(tentativas):
        try:
            r = requests.get(url, params=params, headers={"User-Agent": UA}, timeout=timeout)
            r.raise_for_status()
            return r.json()
        except requests.RequestException:
            if k == tentativas - 1:
                raise


# ---------------------------------------------------------------- busca
def commons(q: str, tipo: str, n: int = 8) -> list[dict]:
    filtro = "filetype:video" if tipo == "video" else "filetype:bitmap"
    js = _get(COMMONS, {"action": "query", "format": "json", "generator": "search", "gsrnamespace": 6,
                        "gsrsearch": f"{q} {filtro}", "gsrlimit": n, "prop": "imageinfo|categories", "cllimit": 8,
                        "iiprop": "url|size|mime|extmetadata", "iiurlwidth": 1600,
                        "iiextmetadatafilter": "LicenseShortName|License|Artist|ImageDescription|ObjectName"})
    out = []
    for p in (js.get("query") or {}).get("pages", {}).values():
        ii = (p.get("imageinfo") or [{}])[0]
        m = ii.get("extmetadata") or {}
        lic = (m.get("License") or {}).get("value") or (m.get("LicenseShortName") or {}).get("value", "")
        if not licenca_ok(lic):
            continue
        video = str(ii.get("mime", "")).startswith(("video/", "application/ogg"))
        if video and not (2.5 <= float(ii.get("duration") or 0) <= 900):
            continue
        if min(ii.get("width") or 0, ii.get("height") or 0) < (360 if video else 600):
            continue
        out.append({"fonte": "Wikimedia Commons", "tipo": "video" if video else "foto",
                    "titulo": p.get("title", "").replace("File:", ""),
                    "descricao": _limpo((m.get("ImageDescription") or {}).get("value", "")),
                    "categorias": [c["title"].replace("Category:", "") for c in p.get("categories", [])][:6],
                    "autor": _limpo((m.get("Artist") or {}).get("value", ""), 60) or "autor desconhecido",
                    "licenca": (m.get("LicenseShortName") or {}).get("value", lic),
                    "url": ii.get("url") if video else (ii.get("thumburl") or ii.get("url")),
                    "thumb": re.sub(r"/\d+px-", "/480px-", ii.get("thumburl") or "") or ii.get("url"),
                    "pagina": ii.get("descriptionurl", ""), "w": ii.get("width"), "h": ii.get("height"),
                    "duracao": float(ii.get("duration") or 0)})
    return out


def openverse(q: str, n: int = 8) -> list[dict]:
    js = _get(OPENVERSE, {"q": q, "license": "cc0,pdm,by,by-sa", "page_size": n, "size": "large", "mature": "false"})
    out = []
    for r in js.get("results", []):
        lic = f"{r.get('license', '')} {r.get('license_version', '')}".strip()
        if not licenca_ok(r.get("license", "")) or (r.get("width") or 0) < 900:
            continue
        out.append({"fonte": f"Openverse/{r.get('source', '')}", "tipo": "foto", "titulo": r.get("title", ""),
                    "descricao": "", "categorias": [t.get("name", "") for t in (r.get("tags") or [])][:8],
                    "autor": (r.get("creator") or "autor desconhecido")[:60], "licenca": ("CC " + lic.upper()).replace("CC CC0", "CC0"),
                    "url": r.get("url"), "thumb": r.get("thumbnail") or r.get("url"),
                    "pagina": r.get("foreign_landing_url", ""), "w": r.get("width"), "h": r.get("height"),
                    "duracao": 0.0})
    return out


PIXABAY = "https://pixabay.com/api/"


def pixabay(q: str, tipo: str, n: int = 6) -> list[dict]:
    """Pixabay (PIXABAY_API_KEY, grátis): fotos e vídeos atuais; licença do Pixabay permite uso comercial e edição."""
    from .util import chave
    k = chave("PIXABAY_API_KEY")
    if not k:
        return []
    url = PIXABAY + ("videos/" if tipo == "video" else "")
    prm = {"key": k, "q": q[:100], "per_page": max(3, n), "safesearch": "true", "lang": "en"}
    if tipo != "video":
        prm.update({"image_type": "photo", "min_width": 1000})
    js = _get(url, prm)
    out = []
    for h in js.get("hits", []):
        base = {"fonte": "Pixabay", "titulo": h.get("tags", ""), "descricao": "", "categorias": (h.get("tags") or "").split(", "),
                "autor": (h.get("user") or "autor desconhecido")[:60], "licenca": "Licença Pixabay", "pagina": h.get("pageURL", "")}
        if tipo == "video":
            vs = h.get("videos") or {}
            v = vs.get("large") if (vs.get("large") or {}).get("url") else vs.get("medium") or {}
            if not v.get("url"):
                continue
            out.append({**base, "tipo": "video", "url": v["url"], "thumb": v.get("thumbnail") or (vs.get("tiny") or {}).get("thumbnail"),
                        "w": v.get("width"), "h": v.get("height"), "duracao": float(h.get("duration") or 0)})
        else:
            out.append({**base, "tipo": "foto", "url": h.get("largeImageURL"), "thumb": h.get("webformatURL"),
                        "w": h.get("imageWidth"), "h": h.get("imageHeight"), "duracao": 0.0})
    return out


def candidatos(buscas: list[str], prefere: str) -> list[dict]:
    """Junta os bancos intercalados (vídeo da Commons, foto da Commons, foto do Openverse...), sem repetir.
    Intercalar importa: em buscas genéricas a Commons traz muita foto de arquivo antiga e o Openverse,
    foto atual; a IA de visão só vê os primeiros candidatos."""
    vistos, listas = set(), []
    for q in buscas[:2]:
        fontes = ([("pxv", lambda: pixabay(q, "video", 6)), ("video", lambda: commons(q, "video", 6))] if prefere == "video" else [])
        fontes += [("pxf", lambda: pixabay(q, "foto", 6)), ("foto", lambda: commons(q, "foto", 6)), ("ov", lambda: openverse(q, 6))]
        for _, busca in fontes:  # cada banco por conta própria: um fora do ar não derruba os outros
            try:
                listas.append([c for c in busca() if c["url"] and serve(c)])
            except Exception as e:
                log(f"  mídia: busca '{q}' falhou ({str(e)[:80]})")
                listas.append([])
    out = []
    for k in range(max([len(l) for l in listas] or [0])):
        for l in listas:
            if k < len(l) and l[k]["url"] not in vistos:
                vistos.add(l[k]["url"]); out.append(l[k])
    return out[:14]


# ---------------------------------------------------------------- IA: buscas e escolha
def _prompt_buscas(cenas: list[dict], tema: str) -> str:
    linhas = "\n".join(f'{i}. [{sc["id"]}] {sc["text"]}' for i, sc in enumerate(cenas))
    return f"""Tema do vídeo: "{tema}". Para CADA cena abaixo, diga o que deve aparecer na tela como foto ou vídeo REAL,
ligado especificamente à frase da cena (a pessoa citada, a empresa, o produto, o lugar, o objeto concreto).
Escreva 2 buscas curtas EM INGLÊS (2 a 4 palavras, nomes próprios primeiro) para bancos de imagens livres (Wikimedia Commons):
a 1ª bem específica (a pessoa, empresa ou produto citado), a 2ª um pouco mais ampla, mas ainda do assunto da frase.
"tipo": "video" se movimento ajuda (robôs andando, foguete decolando, fábrica, trânsito), senão "foto".
Se a frase for abstrata e não houver nada concreto e específico para mostrar, use "buscas": [].

CENAS:
{linhas}

Responda SOMENTE com JSON: {{"cenas": [{{"id": "id da cena", "buscas": ["...", "..."], "tipo": "foto|video"}}]}}"""


def _prompt_visao(sc: dict, cands: list[dict]) -> str:
    lista = "\n".join(f'imagem {i}: ({c["tipo"]}) {c["titulo"][:80]}' for i, c in enumerate(cands))
    return f"""Frase narrada na cena de um vídeo: "{sc['text']}"
A imagem anexa é um mosaico com {len(cands)} fotos numeradas no canto (quadrado amarelo: 0, 1, 2...). Títulos:
{lista}

Escolha a imagem que MOSTRA o assunto desta frase:
- se a frase cita algo específico (pessoa, empresa, produto, lugar), a imagem tem que mostrar esse algo;
- se a frase fala de algo geral (trabalhadores, escritório, fábrica, robôs, data center, dinheiro), uma foto real e atual desse assunto serve.
Recuse: sem relação com a frase, diagrama, gráfico, mapa, documento, texto, logotipo pequeno, arte abstrata, foto antiga em preto e branco
quando a frase fala do presente, imagem borrada ou feia. Prefira a mais bonita e nítida entre as que servem.
Responda SOMENTE com JSON: {{"escolha": número ou -1, "motivo": "curto"}}"""


def _prompt_escolha(sc: dict, cands: list[dict]) -> str:
    lista = "\n".join(f'{i}. ({c["tipo"]}) título: {c["titulo"][:90]} | descrição: {c["descricao"][:140]} | categorias: {", ".join(c["categorias"])[:140]}'
                      for i, c in enumerate(cands))
    return f"""Frase narrada na cena: "{sc['text']}"
Candidatos de bancos de imagens livres:
{lista}

Escolha o candidato que mostra o assunto DESTA frase:
- se a frase cita algo específico (uma pessoa, empresa, produto, lugar), a imagem tem que ser desse algo (outra pessoa/produto não serve);
- se a frase fala de algo geral (trabalhadores, escritórios, fábricas, robôs industriais, data centers, dinheiro), uma foto/vídeo
  real desse assunto serve.
Não serve: imagem sem relação com a frase, diagrama, gráfico, mapa, documento escaneado, logotipo minúsculo, arte abstrata,
foto histórica quando a frase fala do presente. Prefira vídeo quando ele for tão bom quanto a foto. Se nenhum servir, responda -1.
Responda SOMENTE com JSON: {{"escolha": número, "motivo": "curto"}}"""


# ---------------------------------------------------------------- download
def _baixar(url: str, dst: Path, limite_mb: int = 80) -> Path:
    with requests.get(url, headers={"User-Agent": UA}, timeout=60, stream=True) as r:
        r.raise_for_status()
        tam = 0
        with open(dst, "wb") as f:
            for bloco in r.iter_content(1 << 16):
                tam += len(bloco)
                if tam > limite_mb << 20:
                    raise RuntimeError(f"arquivo maior que {limite_mb} MB")
                f.write(bloco)
    return dst


def quadros_video(src: Path, pasta: Path, dur: float, w: int, h: int, fps: int, inicio: float | None = None) -> int:
    """Extrai `dur` segundos do vídeo como JPGs já no tamanho do quadro (corte central, sem distorcer)."""
    pasta.mkdir(parents=True, exist_ok=True)
    tot = _duracao(src)
    ini = inicio if inicio is not None else max(0.0, min(tot * 0.15, tot - dur))
    vf = f"scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},fps={fps}"
    if tot < dur:  # vídeo curto: repete (vai e volta) até cobrir a cena
        vf = f"split[a][b];[b]reverse[r];[a][r]concat=n=2:v=1:a=0,loop=-1:size=32767,trim=duration={dur:.2f}," + vf
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{ini:.2f}", "-i", str(src), "-t", f"{dur:.2f}",
                    "-vf", vf, "-q:v", "3", "-an", str(pasta / "q%04d.jpg")], check=True)
    return len(list(pasta.glob("q*.jpg")))


def _duracao(p: Path) -> float:
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(p)],
                       capture_output=True, text=True)
    try:
        return float(r.stdout.strip())
    except ValueError:
        return 0.0


def credito(c: dict) -> str:
    rot = "Vídeo" if c["tipo"] == "video" else "Foto"
    return f"{rot}: {c['autor']} / {c['fonte'].split('/')[0]} ({c['licenca']})"


def miniatura(url: str, lado: int = 400):
    """Baixa a miniatura (imagem PIL pequena) ou None."""
    import io
    from PIL import Image
    try:
        r = requests.get(url, headers={"User-Agent": UA}, timeout=20)
        r.raise_for_status()
        im = Image.open(io.BytesIO(r.content)).convert("RGB")
        im.thumbnail((lado, lado))
        return im
    except Exception:
        return None


def mosaico(ims: list) -> str:
    """Junta as miniaturas numa grade 3x2 com o número de cada uma (uma imagem só para o modelo de visão)."""
    import base64
    import io
    from PIL import Image, ImageDraw, ImageFont
    c, cel = 3, 400
    lin = (len(ims) + c - 1) // c
    folha = Image.new("RGB", (c * cel, lin * cel), (20, 20, 20))
    try:
        fonte = ImageFont.truetype("arial.ttf", 56)
    except Exception:
        fonte = ImageFont.load_default()
    for i, im in enumerate(ims):
        x, y = (i % c) * cel, (i // c) * cel
        folha.paste(im, (x + (cel - im.width) // 2, y + (cel - im.height) // 2))
        d = ImageDraw.Draw(folha)
        d.rectangle([x, y, x + 74, y + 74], fill=(255, 210, 0))
        d.text((x + 20, y + 6), str(i), fill=(0, 0, 0), font=fonte)
    b = io.BytesIO(); folha.save(b, "JPEG", quality=80)
    return "data:image/jpeg;base64," + base64.b64encode(b.getvalue()).decode()


LETRAS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"


def mosaico_lote(linhas: list[list], cel: int = 260) -> str:
    """Uma linha por cena (letra A, B, C...) e os candidatos dela numerados (A0, A1...): uma imagem para o vídeo todo."""
    import base64
    import io
    from PIL import Image, ImageDraw, ImageFont
    cols = max(len(l) for l in linhas)
    folha = Image.new("RGB", (cols * cel, len(linhas) * cel), (20, 20, 20))
    try:
        fonte = ImageFont.truetype("arial.ttf", 40)
    except Exception:
        fonte = ImageFont.load_default()
    d = ImageDraw.Draw(folha)
    for r, ims in enumerate(linhas):
        for c, im in enumerate(ims):
            x, y = c * cel, r * cel
            if im is not None:
                im = im.copy(); im.thumbnail((cel - 6, cel - 6))
                folha.paste(im, (x + (cel - im.width) // 2, y + (cel - im.height) // 2))
            d.rectangle([x, y, x + 84, y + 50], fill=(255, 210, 0))
            d.text((x + 8, y + 4), f"{LETRAS[r]}{c}", fill=(0, 0, 0), font=fonte)
    b = io.BytesIO(); folha.save(b, "JPEG", quality=78)
    return "data:image/jpeg;base64," + base64.b64encode(b.getvalue()).decode()


def _prompt_lote(cenas: list[dict], vis: dict) -> str:
    linhas = "\n".join(f'Linha {LETRAS[i]}: "{sc["text"]}" | candidatos: '
                        + "; ".join(f'{LETRAS[i]}{k} ({c["tipo"]}) {c["titulo"][:50]}' for k, c in enumerate(vis[sc["id"]]))
                        for i, sc in enumerate(cenas))
    return f"""A imagem anexa é um mosaico: cada LINHA é uma cena de um vídeo (A, B, C...) e cada quadro tem um código no canto
(quadrado amarelo, ex.: B2 = cena B, candidato 2). Frases e títulos:
{linhas}

Para CADA linha, escolha o candidato que MOSTRA o assunto da frase daquela linha:
- se a frase cita algo específico (pessoa, empresa, produto, lugar), o quadro tem que mostrar esse algo;
- se a frase fala de algo geral (trabalhadores, escritório, fábrica, robôs, data center, dinheiro), uma foto/vídeo real e atual desse assunto serve.
Recuse: sem relação com a frase, diagrama, gráfico, mapa, documento, texto, logotipo pequeno, arte abstrata, foto antiga em preto e branco
quando a frase fala do presente, imagem borrada ou feia. Prefira a mais bonita e nítida entre as que servem. Se nenhum servir, -1.
Responda SOMENTE com JSON: {{"A": número ou -1, "B": número ou -1, ...}}"""


def escolher_lote(cenas: list[dict], por_cena: dict, cfg: dict) -> dict:
    """Uma chamada de visão para o vídeo todo (os modelos grátis têm limite por minuto e por dia).
    Até 8 cenas por mosaico. Sem visão disponível, nenhuma cena ganha mídia (ou decide pelo título, se configurado)."""
    import time
    from .llm import gerar_visao_json
    out = {}
    usar_visao = (cfg.get("midia") or {}).get("visao", True)
    for ini in range(0, len(cenas), 8):
        bloco = cenas[ini:ini + 8]
        vis, ims = {}, []
        for sc in bloco:
            cs = [c for c in por_cena[sc["id"]] if c.get("thumb")][:5]
            mini = [miniatura(c["thumb"], 260) for c in cs] if usar_visao else []
            par = [(c, m) for c, m in zip(cs, mini) if m is not None]
            vis[sc["id"]] = [c for c, _ in par]
            ims.append([m for _, m in par] or [None])
        feito = False
        if usar_visao and any(vis.values()):
            for tentativa in range(3):
                try:
                    esc, modelo = gerar_visao_json(_prompt_lote(bloco, vis), [mosaico_lote(ims)], cfg, max_tokens=500)
                    for i, sc in enumerate(bloco):
                        try:
                            k = int(esc.get(LETRAS[i], -1))
                        except (TypeError, ValueError):
                            k = -1
                        out[sc["id"]] = por_cena[sc["id"]].index(vis[sc["id"]][k]) if 0 <= k < len(vis[sc["id"]]) else -1
                    log(f"  mídia: visão ({modelo.split('/')[-1]}) escolheu para {len(bloco)} cena(s) de uma vez")
                    feito = True
                    break
                except Exception as e:
                    log(f"  mídia: visão indisponível ({str(e)[:80]})")
                    if tentativa >= 1:
                        break  # não fica preso: segue para a escolha pelas tags do Pixabay
                    if "per-day" in str(e) or "per day" in str(e):
                        nota("Mídia: a cota diária grátis dos modelos de visão (OpenRouter, 50 pedidos/dia) acabou; cenas sem foto/vídeo hoje.")
                        break
                    if "429" in str(e) and tentativa < 2:
                        time.sleep(30 * (tentativa + 1))  # limite por minuto dos modelos grátis
        if not feito:
            for sc in bloco:  # sem visão: por padrão, nenhuma mídia (não dá para garantir relevância sem ver)
                out[sc["id"]] = escolher(sc, por_cena[sc["id"]], dict(cfg, midia=dict(cfg.get("midia") or {}, visao=False)))
    return out


def escolher(sc: dict, cands: list[dict], cfg: dict) -> int:
    """Escolhe olhando as imagens (modelo de visão); sem visão disponível, decide pelo título/descrição."""
    from .llm import gerar_json, gerar_visao_json
    vis, imgs = [], []
    if (cfg.get("midia") or {}).get("visao", True):
        for c in cands:  # miniaturas baixadas aqui e enviadas embutidas (o provedor nem sempre consegue baixar da Wikimedia)
            if len(vis) >= 6 or not c.get("thumb"):
                continue
            d = miniatura(c["thumb"])
            if d:
                vis.append(c); imgs.append(d)
    if vis:
        import time
        for tentativa in range(2):
            try:
                esc, modelo = gerar_visao_json(_prompt_visao(sc, vis), [mosaico(imgs)], cfg)
                k = int(esc.get("escolha", -1))
                log(f"  mídia [{sc['id']}]: visão ({modelo.split('/')[-1]}) -> {k} ({str(esc.get('motivo', ''))[:70]})")
                return cands.index(vis[k]) if 0 <= k < len(vis) else -1
            except Exception as e:
                log(f"  mídia [{sc['id']}]: visão indisponível ({str(e)[:80]})")
                if tentativa == 0 and "429" in str(e):
                    time.sleep(25)  # limite por minuto dos modelos grátis: espera e tenta de novo
    if not (cfg.get("midia") or {}).get("escolha_sem_ver", False):
        # sem olhar a imagem, só o Pixabay: as tags dele descrevem o conteúdo (Commons/Openverse não garantem)
        px = [c for c in cands if c.get("fonte") == "Pixabay"]
        if not px or not (cfg.get("midia") or {}).get("pixabay_sem_visao", True):
            return -1
        try:
            esc, _, _ = gerar_json(_prompt_escolha(sc, px), cfg, temperatura=0.1, max_tokens=400)
            k = int(esc.get("escolha", -1))
            return cands.index(px[k]) if 0 <= k < len(px) else -1
        except Exception:
            return -1
    try:
        esc, _, _ = gerar_json(_prompt_escolha(sc, cands), cfg, temperatura=0.1, max_tokens=400)
        return int(esc.get("escolha", -1))
    except Exception:
        return -1


def foto_thumb(roteiro: dict, cfg: dict, pasta: Path, creditos: list[dict]) -> dict | None:
    """Foto da thumb do longo: o assunto central (roteiro['thumb_foto']), horizontal e grande, escolhida pela visão.
    Sem visão: a maior foto já escolhida (com visão) para as cenas. Devolve {photo, credito, pagina} ou None."""
    q = str(roteiro.get("thumb_foto") or "").strip()
    titulo = ((roteiro.get("publicacao") or {}).get("youtube") or {}).get("titulo") or roteiro.get("tema", "")
    if isinstance(titulo, list):
        titulo = titulo[0] if titulo else ""
    if q:
        cands = [c for c in candidatos([q], "foto") if (c.get("w") or 0) >= 1000 and (c.get("w") or 0) >= (c.get("h") or 0) * 0.9]
        if cands:
            sc = {"id": "thumb", "text": f'FOTO DE CAPA (thumbnail do YouTube) do vídeo "{titulo}". Precisa mostrar {q} em destaque, '
                                        "nítido, BEM ILUMINADO e colorido, de preferência rosto com expressão ou o produto bem visível; "
                                        "nada de foto pequena, escura, de longe, ambiente vazio ou com texto por cima."}
            k = escolher_lote([sc], {"thumb": cands}, cfg).get("thumb", -1)
            if 0 <= k < len(cands):
                c = cands[k]
                try:
                    ext = Path(c["url"].split("?")[0]).suffix.lower() or ".jpg"
                    arq = _baixar(c["url"], pasta / "midia" / f"_thumb{ext}")
                    log(f"  thumb: foto '{c['titulo'][:60]}' ({c['licenca']})")
                    return {"photo": arq.resolve().as_uri(), "credito": credito(c).replace("Foto:", "Foto da capa:"), "pagina": c["pagina"]}
                except Exception as e:
                    log(f"  thumb: não consegui baixar a foto ({str(e)[:80]})")
    fotos = []
    for ch in roteiro.get("chapters", []):
        for sc in ch.get("scenes", []):
            prm = sc.get("params") or {}
            if prm.get("_photo"):
                fotos.append(prm)
    if fotos:
        prm = fotos[0]
        return {"photo": prm["_photo"], "credito": str(prm.get("_credit", "")).replace("Foto:", "Foto da capa:"), "pagina": ""}
    return None


# ---------------------------------------------------------------- orquestração
def aplicar(roteiro: dict, cfg: dict, pasta: Path, durs: dict[str, float], w: int, h: int, fps: int) -> list[dict]:
    """Escolhe e baixa mídia para as cenas; grava params._photo / params._video / params._credit.
    Devolve a lista de créditos (para a descrição e o relatório)."""
    from .llm import gerar_json
    mcfg = cfg.get("midia") or {}
    if not mcfg.get("ativo", True):
        return []
    cenas = [sc for ch in roteiro.get("chapters", []) for sc in ch.get("scenes", [])]
    alvo = [sc for sc in cenas if sc.get("template") != "cta"]  # o CTA fica limpo (pergunta + opções)
    if not alvo:
        return []
    try:
        plano, _, _ = gerar_json(_prompt_buscas(alvo, roteiro.get("tema", "")), cfg, temperatura=0.3, max_tokens=3000)
    except Exception as e:
        nota(f"Mídia: a IA não montou as buscas ({str(e)[:100]}); vídeo sem fotos.")
        return []
    por_id = {str(c.get("id")): c for c in (plano.get("cenas") or []) if isinstance(c, dict)}
    dest = pasta / "midia"
    dest.mkdir(parents=True, exist_ok=True)
    creditos, max_cenas = [], int(mcfg.get("max_cenas", 99))
    por_cena = {}
    for sc in alvo:
        p = por_id.get(sc["id"]) or {}
        buscas = [str(b) for b in (p.get("buscas") or []) if str(b).strip()]
        if buscas:
            cands = candidatos(buscas, "video" if p.get("tipo") == "video" else "foto")
            if cands:
                por_cena[sc["id"]] = cands
    escolhas = escolher_lote([sc for sc in alvo if sc["id"] in por_cena], por_cena, cfg)
    for sc in alvo:
        if len(creditos) >= max_cenas or sc["id"] not in por_cena:
            continue
        cands, k = por_cena[sc["id"]], escolhas.get(sc["id"], -1)
        if not 0 <= k < len(cands):
            log(f"  mídia [{sc['id']}]: nenhum candidato mostra o assunto da frase; cena sem mídia")
            continue
        c = cands[k]
        try:
            ext = Path(c["url"].split("?")[0]).suffix.lower() or (".webm" if c["tipo"] == "video" else ".jpg")
            arq = _baixar(c["url"], dest / f"{sc['id']}{ext}")
            prm = sc.setdefault("params", {})
            if c["tipo"] == "video":
                dur = float(durs.get(sc["id"], 6)) + 0.6
                n = quadros_video(arq, dest / sc["id"], dur, w, h, fps)
                if n < 5:
                    raise RuntimeError("vídeo sem quadros")
                prm["_video"] = {"dir": (dest / sc["id"]).resolve().as_uri() + "/", "n": n, "fps": fps}
                arq.unlink(missing_ok=True)
            else:
                prm["_photo"] = arq.resolve().as_uri()
                if (c.get("h") or 0) > (c.get("w") or 1) * 0.9:
                    prm["_focus"] = "50% 12%"  # foto em pé (geralmente pessoa): não corta a cabeça
            prm["_credit"] = credito(c)
            creditos.append({"cena": sc["id"], "credito": credito(c), **{k2: c[k2] for k2 in ("tipo", "titulo", "autor", "licenca", "fonte", "pagina")}})
            log(f"  mídia [{sc['id']}]: {c['tipo']} '{c['titulo'][:60]}' ({c['licenca']})")
        except Exception as e:
            log(f"  mídia [{sc['id']}]: falhou ao baixar/preparar ({str(e)[:90]})")
    nota(f"Mídia: {len(creditos)} de {len(alvo)} cenas com foto/vídeo real de licença livre (créditos na descrição).")
    return creditos
