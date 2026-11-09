"""Render determinístico: Chromium (Playwright) desenha cada quadro com renderAt(t) e o ffmpeg codifica."""
from __future__ import annotations

import base64
import json
import math
import os
import subprocess
from concurrent.futures import ProcessPoolExecutor
from multiprocessing import get_context
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from .util import ENGINE, RAIZ, duracao, ffprobe, garantir_gsap, log, nota, run

CARD_DUR = 2.2
CAUDA = 0.45
FINAL_EXTRA = 1.5


# ---------------------------------------------------------------- linha do tempo
def _logo(v: dict) -> dict:
    """Marca d'água em imagem (visual.marca_logo): caminho relativo à raiz do repo ou absoluto."""
    p = (v.get("marca_logo") or "").strip()
    if not p:
        return {}
    f = Path(p) if Path(p).is_absolute() else ENGINE.parent / p
    if not f.exists():
        nota(f"marca_logo não encontrada: {p}; vídeo sai sem marca d'água.")
        return {}
    return {"brandLogo": f.resolve().as_uri(), "brandLogoOpacity": float(v.get("marca_opacidade", 0.5))}


def montar_timeline(roteiro: dict, narr: dict, cfg: dict) -> dict:
    longo = roteiro["formato"] == "longo"
    W, H = (1920, 1080) if longo else (1080, 1920)
    segs, caps = [], []
    t = 0.0
    nch = len(roteiro["chapters"])
    for ci, ch in enumerate(roteiro["chapters"]):
        if longo and ci > 0:
            segs.append({"id": f"cap{ci + 1}", "kind": "chapter", "start": t, "dur": CARD_DUR, "num": ci + 1, "total": nch,
                         "title": ch["title"], "chapterTitle": ch["title"]})
            t += CARD_DUR
        for sc in ch["scenes"]:
            a = narr["cenas"][sc["id"]]
            d = a["dur"] + CAUDA
            seg = {"id": sc["id"], "kind": "scene", "template": sc.get("template", "headline"), "params": sc.get("params", {}),
                   "start": t, "dur": d, "wav": a["wav"], "source": sc.get("source", ""), "text": sc["text"],
                   "chapterTitle": (f"Cap {ci + 1} · {ch['title']}" if longo else (cfg["tema"].get("nicho") or ""))}
            segs.append(seg)
            ws = a["words"]
            for g in range(0, len(ws), 4):
                grp = ws[g:g + 4]
                ini = t + grp[0]["s"]
                fim = t + (ws[g + 4]["s"] if g + 4 < len(ws) else min(grp[-1]["e"] + 0.35, d - 0.05))
                caps.append({"start": round(ini, 3), "end": round(max(fim, ini + 0.2), 3),
                             "words": [{"w": x["w"], "s": round(t + x["s"], 3)} for x in grp]})
            t += d
    segs[-1]["dur"] += FINAL_EXTRA
    t += FINAL_EXTRA
    caps.sort(key=lambda c: c["start"])
    for a, b in zip(caps, caps[1:]):
        a["end"] = min(a["end"], b["start"])
    v = cfg["visual"]
    return {"w": W, "h": H, "fps": int(v.get("fps", 30)), "duration": round(t, 3), "segments": segs, "captions": caps,
            "showCaptions": bool(v.get("legendas", True)), "brand": v.get("marca", ""), **_logo(v), "scene3d": roteiro.get("cena3d") or v.get("cena3d") or "",
            "scale3d": float(v.get("escala3d", 0.75)), "brandLogoPeriod": float(v.get("marca_troca_s", 9)),
            "theme": {"accent": v.get("acento", "#ff4f12"), "accent2": v.get("acento2", "#d4ff3a")}}


# ---------------------------------------------------------------- navegador
def _abrir(w, h):
    from playwright.sync_api import sync_playwright
    pw = sync_playwright().start()
    br = pw.chromium.launch(args=["--font-render-hinting=none", "--disable-lcd-text", "--force-color-profile=srgb",
                                  "--hide-scrollbars", "--disable-gpu"])
    pg = br.new_page(viewport={"width": w, "height": h}, device_scale_factor=1)
    pg.goto((ENGINE / "index.html").as_uri())
    pg.wait_for_function("window.boot && window.gsap")
    return pw, br, pg


def _shot(cdp, fmt="jpeg", q=92) -> bytes:
    args = {"format": fmt, "optimizeForSpeed": True}
    if fmt == "jpeg":
        args["quality"] = q
    return base64.b64decode(cdp.send("Page.captureScreenshot", args)["data"])


def _boot(pg, data):
    res = pg.evaluate("d => window.boot(d)", data)
    for sid, err in res.get("errors", []):
        nota(f"Cena {sid}: o modelo de cena falhou ({err[:80]}); usei título simples.")
    return res


# ---------------------------------------------------------------- CRIVO 5
def previa(data: dict, pasta: Path) -> list:
    garantir_gsap()
    pw, br, pg = _abrir(data["w"], data["h"])
    try:
        _boot(pg, data)
        issues = pg.evaluate("() => window.audit()")
        cdp = pg.context.new_cdp_session(pg)
        thumbs = []
        for s in data["segments"]:
            for frac in (0.4, 0.85):
                t = s["start"] + min(s["dur"] - 0.3, s["dur"] * frac)
                pg.evaluate("t => window.renderAt(t)", t)
                im = Image.open(__import__("io").BytesIO(_shot(cdp)))
                thumbs.append((s["id"], im.convert("RGB")))
    finally:
        br.close(); pw.stop()
    folha(thumbs, pasta / "previa_crivo5.png", 2 * (4 if data["w"] > data["h"] else 6))
    return issues


def folha(thumbs, out: Path, cols: int):
    if not thumbs:
        return
    w0, h0 = thumbs[0][1].size
    tw = 400 if w0 > h0 else 225
    th = int(tw * h0 / w0)
    rows = math.ceil(len(thumbs) / cols)
    sheet = Image.new("RGB", (cols * tw, rows * (th + 22)), (12, 12, 14))
    d = ImageDraw.Draw(sheet)
    try:
        f = ImageFont.truetype(str(RAIZ / "fonts" / "figtree_Figtree-Variable.ttf"), 15)
    except Exception:
        f = ImageFont.load_default()
    for i, (lab, im) in enumerate(thumbs):
        x, y = (i % cols) * tw, (i // cols) * (th + 22)
        sheet.paste(im.resize((tw, th), Image.LANCZOS), (x, y + 22))
        d.text((x + 6, y + 3), str(lab)[:40], fill=(230, 230, 230), font=f)
    sheet.save(out)


# ---------------------------------------------------------------- render completo
def _worker(args):
    data_path, f0, f1, out = args
    data = json.loads(Path(data_path).read_text(encoding="utf-8"))
    fps = data["fps"]
    pw, br, pg = _abrir(data["w"], data["h"])
    try:
        pg.evaluate("d => window.boot(d)", data)
        cdp = pg.context.new_cdp_session(pg)
        enc = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "image2pipe", "-framerate", str(fps), "-c:v", "mjpeg", "-i", "-",
                                "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p", "-r", str(fps),
                                "-g", str(fps * 2), "-x264-params", "keyint=" + str(fps * 2), str(out)], stdin=subprocess.PIPE)
        passo = max(1, (f1 - f0) // 20)
        for f in range(f0, f1):
            pg.evaluate("t => window.renderAt(t)", f / fps)
            enc.stdin.write(_shot(cdp))
            if (f - f0 + 1) % passo == 0 or f == f1 - 1:
                print(f"  render {Path(out).stem}: {f - f0 + 1}/{f1 - f0} quadros", flush=True)
        enc.stdin.close()
        enc.wait()
        if enc.returncode:
            raise RuntimeError("ffmpeg falhou no pedaço " + str(out))
    finally:
        br.close(); pw.stop()
    return str(out)


def render(data: dict, audio: Path, pasta: Path, nome: str, workers: int = 0) -> Path:
    garantir_gsap()
    fps = data["fps"]
    nf = int(round(data["duration"] * fps))
    n = workers or max(1, min(8, os.cpu_count() or 2))
    dp = pasta / "_timeline.json"
    dp.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    partes = []
    lim = [round(nf * k / n) for k in range(n + 1)]
    jobs = [(str(dp), lim[k], lim[k + 1], str(pasta / f"_parte_{k:02d}.mp4")) for k in range(n) if lim[k + 1] > lim[k]]
    log(f"render: {nf} quadros a {fps} fps em {len(jobs)} processo(s)")
    with ProcessPoolExecutor(max_workers=len(jobs), mp_context=get_context("spawn")) as ex:
        partes = list(ex.map(_worker, jobs))
    lst = pasta / "_partes.txt"
    lst.write_text("".join(f"file '{Path(p).name}'\n" for p in partes), encoding="utf-8")
    out = pasta / nome
    run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", lst, "-i", audio, "-map", "0:v", "-map", "1:a",
         "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-ar", "44100", "-shortest", "-movflags", "+faststart", out])
    for p in partes:
        Path(p).unlink(missing_ok=True)
    return out


# ---------------------------------------------------------------- CRIVO 6
def conferir(video: Path, data: dict, pasta: Path) -> dict:
    info = ffprobe(video)
    v = next(s for s in info["streams"] if s["codec_type"] == "video")
    a = [s for s in info["streams"] if s["codec_type"] == "audio"]
    d = float(info["format"]["duration"])
    res = {"largura": v["width"], "altura": v["height"], "fps": v.get("r_frame_rate"), "duracao": round(d, 2),
           "audio": bool(a), "tamanho_mb": round(video.stat().st_size / 2**20, 1)}
    ok = v["width"] == data["w"] and v["height"] == data["h"] and bool(a) and abs(d - data["duration"]) < 1.5
    res["ok"] = ok
    if not ok:
        nota(f"CRIVO 6: conferência do arquivo falhou: {res}")
    cols = 6 if data["w"] > data["h"] else 10
    run(["ffmpeg", "-v", "error", "-y", "-i", video, "-vf",
         f"fps=1/5,scale={320 if data['w'] > data['h'] else 180}:-1,tile={cols}x{math.ceil(d / 5 / cols)}",
         "-frames:v", "1", pasta / "folha_crivo6.png"])
    return res


def previa_leve(video: Path, pasta: Path, limite_mb: float) -> Path | None:
    """Versão que abre no celular: mesma resolução, bitrate calculado para caber no limite."""
    if video.stat().st_size / 2**20 <= limite_mb:
        return None
    d = duracao(video)
    kbps = max(250, int((limite_mb * 0.92 * 8 * 1024) / d - 128))
    out = pasta / (video.stem + f"_previa_{int(limite_mb)}mb.mp4")
    run(["ffmpeg", "-v", "error", "-y", "-i", video, "-c:v", "libx264", "-preset", "slow", "-b:v", f"{kbps}k",
         "-maxrate", f"{int(kbps * 1.4)}k", "-bufsize", f"{kbps * 3}k", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "128k",
         "-movflags", "+faststart", out])
    if out.stat().st_size / 2**20 > limite_mb:
        nota(f"A prévia ficou com {out.stat().st_size / 2**20:.1f} MB (acima de {limite_mb} MB).")
    return out


# ---------------------------------------------------------------- thumbnails (CRIVO 7)
def thumbs(info: dict, cfg: dict, pasta: Path, curto: bool) -> list[Path]:
    garantir_gsap()
    v = cfg["visual"]
    alvos = [("thumb_1280x720.jpg", 1280, 720)] + ([("capa_1080x1920.jpg", 1080, 1920)] if curto else [])
    saidas = []
    for nome, w, h in alvos:
        pw, br, pg = _abrir(w, h)
        try:
            dd = dict(info, w=w, h=h, theme={"accent": v.get("acento"), "accent2": v.get("acento2")})
            res = pg.evaluate("d => window.bootThumb(d)", dd)
            png = pg.screenshot(type="png")
        finally:
            br.close(); pw.stop()
        im = Image.open(__import__("io").BytesIO(png)).convert("RGB")
        im.save(pasta / nome, quality=93)
        im.resize((w // 4, h // 4), Image.LANCZOS).save(pasta / ("_25pct_" + nome.replace(".jpg", ".png")))
        if res["issues"]:
            nota(f"CRIVO 7 ({nome}): {res['issues']}")
        if res["mainFontAt25"] < 18:
            nota(f"CRIVO 7 ({nome}): a palavra principal fica com {res['mainFontAt25']:.0f}px a 25% (pode ficar pequena).")
        saidas.append(pasta / nome)
    return saidas
