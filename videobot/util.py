"""Utilidades comuns: log, ffmpeg, configuração e texto."""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
import unicodedata
import urllib.request
from pathlib import Path

import yaml

RAIZ = Path(__file__).resolve().parent.parent
ENGINE = RAIZ / "engine"
GSAP_URL = "https://cdn.jsdelivr.net/npm/gsap@3.13.0/dist/gsap.min.js"

_T0 = time.time()
NOTAS: list[str] = []  # "o que foi trocado ou não foi possível" — vai para o relatório


def log(*a):
    print(f"[{time.time() - _T0:7.1f}s]", *a, flush=True)


def nota(txt: str):
    """Registra uma troca/limitação para o relatório final."""
    log("NOTA:", txt)
    NOTAS.append(txt)


def run(cmd, **kw):
    kw.setdefault("check", True)
    return subprocess.run([str(c) for c in cmd], **kw)


def ffprobe(path) -> dict:
    out = subprocess.run(["ffprobe", "-v", "error", "-show_format", "-show_streams", "-of", "json", str(path)],
                         capture_output=True, text=True, check=True).stdout
    return json.loads(out)


def duracao(path) -> float:
    return float(ffprobe(path)["format"]["duration"])


def slugify(s: str, n: int = 40) -> str:
    s = unicodedata.normalize("NFD", s).encode("ascii", "ignore").decode()
    s = re.sub(r"[^a-zA-Z0-9]+", "_", s).strip("_").lower()
    return s[:n].strip("_") or "video"


def sem_acento(s: str) -> str:
    return unicodedata.normalize("NFD", s).encode("ascii", "ignore").decode()


def tokens(s: str) -> list[str]:
    s = sem_acento(s.lower())
    return [t for t in re.findall(r"[a-z0-9]+", s)]


def deep_merge(a: dict, b: dict) -> dict:
    out = dict(a)
    for k, v in (b or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def carregar_config(path: Path | None = None, extra: dict | None = None) -> dict:
    cfg = yaml.safe_load((path or RAIZ / "config.yml").read_text(encoding="utf-8"))
    return deep_merge(cfg, extra or {})


THREE_URL = "https://cdn.jsdelivr.net/npm/three@0.160.0/build/three.min.js"


def garantir_three():
    alvo = ENGINE / "vendor" / "three.min.js"
    if alvo.exists() and alvo.stat().st_size > 100_000:
        return alvo
    alvo.parent.mkdir(parents=True, exist_ok=True)
    log("baixando Three.js 0.160.0 (licença MIT)")
    with urllib.request.urlopen(THREE_URL, timeout=60) as r:
        alvo.write_bytes(r.read())
    return alvo


def garantir_gsap():
    garantir_three()
    alvo = ENGINE / "vendor" / "gsap.min.js"
    if alvo.exists() and alvo.stat().st_size > 10_000:
        return alvo
    alvo.parent.mkdir(parents=True, exist_ok=True)
    log("baixando GSAP 3.13.0 (licença padrão GreenSock, gratuita)")
    with urllib.request.urlopen(GSAP_URL, timeout=60) as r:
        alvo.write_bytes(r.read())
    return alvo


def chave(nome: str) -> str | None:
    """Lê uma chave do ambiente sem nunca imprimi-la."""
    v = os.environ.get(nome, "").strip()
    return v or None


def escrever_json(path: Path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


def ler_json(path: Path, padrao=None):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception:
        return padrao


def resumo_github(md: str):
    """Escreve no resumo da execução do GitHub Actions, se houver."""
    p = os.environ.get("GITHUB_STEP_SUMMARY")
    if p:
        with open(p, "a", encoding="utf-8") as f:
            f.write(md + "\n")


def falhar(msg: str):
    log("ERRO:", msg)
    resumo_github(f"## ❌ Vídeo não gerado\n\n{msg}\n")
    sys.exit(1)
