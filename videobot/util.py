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


def etapa(chave_: str, titulo: str):
    """Marca o início de uma etapa (a interface local usa esta linha para o passo a passo)."""
    log(f"== ETAPA {chave_}: {titulo}")


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


CONFIG_LOCAL = RAIZ / "config.local.yml"  # ajustes salvos pela interface local (fora do git)


def carregar_config(path: Path | None = None, extra: dict | None = None) -> dict:
    cfg = yaml.safe_load((path or RAIZ / "config.yml").read_text(encoding="utf-8"))
    if path is None and CONFIG_LOCAL.exists():
        cfg = deep_merge(cfg, yaml.safe_load(CONFIG_LOCAL.read_text(encoding="utf-8")) or {})
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


THREE_JSM = "https://cdn.jsdelivr.net/npm/three@0.160.0/examples/jsm/"
EXTRAS_3D = ("utils/BufferGeometryUtils.js", "utils/SkeletonUtils.js", "loaders/GLTFLoader.js",
             "environments/RoomEnvironment.js", "geometries/RoundedBoxGeometry.js")
# modelos 3D prontos (CC0) embutidos como base64: o motor abre em file://, onde fetch de arquivo é bloqueado
MODELOS_3D = {
    "robo": "https://cdn.jsdelivr.net/gh/mrdoob/three.js@r160/examples/models/gltf/RobotExpressive/RobotExpressive.glb",
}


def modulo_para_script(src: str) -> str:
    """Converte um módulo ES dos exemplos do Three.js em script comum que usa o THREE global.

    import {A, B} from 'three'        -> const {A, B} = THREE;
    import {x} from '../utils/Y.js'    -> const {x} = THREEX;
    export function f / export {A, B}  -> registra em window.THREEX
    """
    def nomes(lista: str) -> str:
        return ", ".join(n.strip().replace(" as ", ": ") for n in lista.split(",") if n.strip())

    src = re.sub(r"import\s*\{([^}]*)\}\s*from\s*'three';", lambda m: f"const {{ {nomes(m.group(1))} }} = THREE;", src)
    src = re.sub(r"import\s*\{([^}]*)\}\s*from\s*'[^']+';", lambda m: f"const {{ {nomes(m.group(1))} }} = window.THREEX;", src)
    exportados = re.findall(r"^export\s+(?:function|class|const)\s+(\w+)", src, re.M)
    src = re.sub(r"^export\s+(function|class|const)\s", r"\1 ", src, flags=re.M)
    for m in re.finditer(r"^export\s*\{([^}]*)\};?", src, re.M):
        exportados += [n.strip().split(" as ")[-1] for n in m.group(1).split(",") if n.strip()]
    src = re.sub(r"^export\s*\{[^}]*\};?", "", src, flags=re.M)
    if re.search(r"^\s*(import|export)\s", src, re.M):
        raise ValueError("módulo com import/export que o conversor não entende")
    return ("(function () {\n'use strict';\nwindow.THREEX = window.THREEX || {};\n" + src
            + f"\nObject.assign(window.THREEX, {{ {', '.join(dict.fromkeys(exportados))} }});\n}})();\n")


def garantir_extras3d():
    """vendor/three-extras.js (GLTFLoader, RoomEnvironment...) e vendor/modelos3d.js (GLBs em base64)."""
    import base64
    vend = ENGINE / "vendor"
    vend.mkdir(parents=True, exist_ok=True)
    ext = vend / "three-extras.js"
    if not (ext.exists() and ext.stat().st_size > 50_000 and "RoundedBoxGeometry" in ext.read_text(encoding="utf-8")):
        log("baixando extras do Three.js 0.160.0 (GLTFLoader, RoomEnvironment; licença MIT)")
        partes = []
        for arq in EXTRAS_3D:
            with urllib.request.urlopen(THREE_JSM + arq, timeout=60) as r:
                partes.append(f"// {arq}\n" + modulo_para_script(r.read().decode("utf-8")))
        ext.write_text("\n".join(partes), encoding="utf-8")
    mod = vend / "modelos3d.js"
    if not (mod.exists() and mod.stat().st_size > 100_000):
        log("baixando modelos 3D (RobotExpressive, CC0)")
        js = ["window.MODELOS3D = {};"]
        for nome, url in MODELOS_3D.items():
            with urllib.request.urlopen(url, timeout=60) as r:
                js.append(f"window.MODELOS3D[{nome!r}] = '{base64.b64encode(r.read()).decode()}';")
        mod.write_text("\n".join(js), encoding="utf-8")
    return ext, mod


def garantir_gsap():
    garantir_three()
    garantir_extras3d()
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
