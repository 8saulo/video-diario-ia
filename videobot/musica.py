"""Trilha de fundo real e de licença livre (Openverse: Jamendo, ccMixter, Freesound...), sem chave de API.

Só CC0 e CC BY (uso comercial e edição liberados), instrumental (títulos com vocal/remix ficam de fora), de 1 a 8 minutos.
Sem internet ou sem resultado, o mixer usa a trilha sintetizada em código (videobot/audio.trilha) como antes.
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

import requests

from .util import log

UA = "video-diario-ia/1.0 (https://github.com/8saulo/video-diario-ia)"
API = "https://api.openverse.org/v1/audio/"
VOCAL = re.compile(r"vocal|voice|sing|lyric|feat\.?|remix|rap\b|acapella|karaoke|podcast|speech|poem", re.I)


def candidatos(q: str, n: int = 12) -> list[dict]:
    r = requests.get(API, params={"q": q, "license": "cc0,by", "category": "music", "page_size": n, "mature": "false"},
                     headers={"User-Agent": UA}, timeout=30)
    r.raise_for_status()
    out = []
    for a in r.json().get("results", []):
        dur = (a.get("duration") or 0) / 1000
        if not (60 <= dur <= 480) or VOCAL.search(a.get("title") or "") or not a.get("url"):
            continue
        out.append({"titulo": (a.get("title") or "sem título")[:60], "autor": (a.get("creator") or "autor desconhecido")[:50],
                    "licenca": ("CC " + f"{a.get('license', '')} {a.get('license_version', '')}".strip().upper()).replace("CC CC0", "CC0"),
                    "url": a["url"], "pagina": a.get("foreign_landing_url", ""), "fonte": a.get("source", ""), "dur": dur})
    return out


def escolher(cfg: dict, pasta: Path, semente: int = 0) -> dict | None:
    """Baixa uma faixa e converte para WAV mono 44,1 kHz. Devolve {wav, credito, pagina, titulo} ou None."""
    mcfg = (cfg.get("visual") or {}).get("musica_real") or {}
    if not mcfg or not mcfg.get("ativo", True):
        return None
    buscas = list(mcfg.get("buscas") or ["electronic", "ambient", "chillout", "cinematic"])
    usadas = set()
    for k in range(len(buscas)):
        q = buscas[(semente + k) % len(buscas)]
        try:
            cands = candidatos(q)
        except Exception as e:
            log(f"  música: busca '{q}' falhou ({str(e)[:70]})")
            continue
        for c in cands[semente % max(1, len(cands)):] + cands[:semente % max(1, len(cands))]:
            if c["url"] in usadas:
                continue
            usadas.add(c["url"])
            mp3 = pasta / "_musica.mp3"
            wav = pasta / "_musica.wav"
            try:
                with requests.get(c["url"], headers={"User-Agent": UA}, timeout=60, stream=True) as r:
                    r.raise_for_status()
                    tam = 0
                    with open(mp3, "wb") as f:
                        for b in r.iter_content(1 << 16):
                            tam += len(b)
                            if tam > 25 << 20:
                                raise RuntimeError("arquivo grande demais")
                            f.write(b)
                subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(mp3), "-ac", "1", "-ar", "44100", "-sample_fmt", "s16", str(wav)], check=True)
            except Exception as e:
                log(f"  música: não consegui baixar '{c['titulo']}' ({str(e)[:70]})")
                continue
            finally:
                mp3.unlink(missing_ok=True)
            log(f"  música: '{c['titulo']}' — {c['autor']} ({c['licenca']}, {c['fonte']})")
            return {"wav": wav, "titulo": "trilha", "credito": f"Música: {c['titulo']} — {c['autor']} ({c['licenca']})", "pagina": c["pagina"]}
    return None
