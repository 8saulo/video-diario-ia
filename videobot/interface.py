"""Interface local no navegador: escolhe opções, edita a configuração e acompanha a execução.

  python -m videobot ui            # abre http://127.0.0.1:8765
  python -m videobot ui --porta 9000 --sem-navegador

Só escuta em 127.0.0.1 (nada fica exposto na rede). A chave do Gemini nunca vai para o navegador:
o servidor só informa se ela existe e usa a chave para listar os modelos disponíveis.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

import yaml

from .util import CONFIG_LOCAL, RAIZ, deep_merge, ler_json

PAGINA = Path(__file__).resolve().parent / "interface.html"
SAIDA = RAIZ / "saida"
CFG_EXEC = SAIDA / "_interface_config.yml"

TIPOS_ARQUIVO = {".mp4": "video/mp4", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png",
                 ".md": "text/markdown; charset=utf-8", ".json": "application/json; charset=utf-8",
                 ".txt": "text/plain; charset=utf-8"}


# ---------------------------------------------------------------- chave
def garantir_chave_no_ambiente() -> bool:
    """Se o processo foi aberto antes do `setx`, busca a chave salva na conta do Windows."""
    if os.environ.get("GEMINI_API_KEY", "").strip():
        return True
    if sys.platform == "win32":
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as k:
                for nome in ("GEMINI_API_KEY", "YOUTUBE_API_KEY"):
                    try:
                        v, _ = winreg.QueryValueEx(k, nome)
                        if str(v).strip() and not os.environ.get(nome):
                            os.environ[nome] = str(v).strip()
                    except OSError:
                        pass
        except OSError:
            pass
    return bool(os.environ.get("GEMINI_API_KEY", "").strip())


# ---------------------------------------------------------------- configuração
def comentarios_do_yaml(texto: str) -> dict[str, str]:
    """Mapeia 'secao.chave' -> comentário da mesma linha (ou das linhas logo acima) do config.yml."""
    ajuda, pilha, pendente = {}, [], []
    for linha in texto.splitlines():
        s = linha.strip()
        if not s:
            pendente = []
            continue
        if s.startswith("#"):
            t = s.lstrip("#").strip()
            if t and not set(t) <= set("-= "):
                pendente.append(t.strip("- ").strip())
            continue
        m = re.match(r"^(\s*)([A-Za-z0-9_]+):(.*)$", linha)
        if not m:
            continue
        ind = len(m.group(1))
        while pilha and pilha[-1][0] >= ind:
            pilha.pop()
        pilha.append((ind, m.group(2)))
        caminho = ".".join(k for _, k in pilha)
        resto = m.group(3)
        com = ""
        mm = re.search(r"\s#\s?(.*)$", resto)
        if mm and resto.count('"') % 2 == 0:
            com = mm.group(1).strip()
        partes = [p for p in pendente if not re.fullmatch(r"[A-ZÇÃÕÉ ()/.\-]+", p)] + ([com] if com else [])
        if partes:
            ajuda[caminho] = " ".join(partes)
        pendente = []
    return ajuda


def diferenca(base, novo):
    """Só o que mudou em relação ao config.yml (vai para config.local.yml)."""
    if isinstance(base, dict) and isinstance(novo, dict):
        out = {}
        for k, v in novo.items():
            if k not in base:
                out[k] = v
            else:
                d = diferenca(base[k], v)
                if d is not _IGUAL:
                    out[k] = d
        return out if out else _IGUAL
    return _IGUAL if base == novo else novo


_IGUAL = object()


def estado_config() -> dict:
    texto = (RAIZ / "config.yml").read_text(encoding="utf-8")
    base = yaml.safe_load(texto)
    local = yaml.safe_load(CONFIG_LOCAL.read_text(encoding="utf-8")) if CONFIG_LOCAL.exists() else {}
    return {"base": base, "local": local or {}, "efetivo": deep_merge(base, local or {}),
            "ajuda": comentarios_do_yaml(texto), "historico": (ler_json(RAIZ / "historico" / "temas.json", []) or [])[-15:][::-1]}


# ---------------------------------------------------------------- modelos do Gemini
_cache_modelos: dict = {}


def listar_modelos() -> dict:
    if not garantir_chave_no_ambiente():
        return {"ok": False, "erro": "GEMINI_API_KEY não encontrada", "texto": [], "tts": []}
    if _cache_modelos.get("t", 0) > time.time() - 600:
        return _cache_modelos["v"]
    from .tts import _gemini
    st, js = _gemini("GET", "/models?pageSize=1000", os.environ["GEMINI_API_KEY"].strip(), timeout=30)
    if st != 200:
        return {"ok": False, "erro": f"o Google respondeu HTTP {st}", "texto": [], "tts": []}
    texto, tts = [], []
    for m in js.get("models", []):
        if "generateContent" not in m.get("supportedGenerationMethods", []):
            continue
        nome = m["name"].split("/")[-1]
        item = {"nome": nome, "titulo": m.get("displayName", nome)}
        if "tts" in nome:
            tts.append(item)
        elif nome.startswith("gemini") and not re.search(r"image|banana|embedding|audio|transcribe|live|vision|robotics|computer|customtools", nome):
            texto.append(item)
    v = {"ok": True, "texto": texto, "tts": tts}
    _cache_modelos.update(t=time.time(), v=v)
    return v


# ---------------------------------------------------------------- execução
class Execucao:
    def __init__(self):
        self.lock = threading.Lock()
        self.proc: subprocess.Popen | None = None
        self.linhas: list[str] = []
        self.status = "parado"  # parado | rodando | ok | erro | interrompido
        self.inicio = self.fim = 0.0
        self.resumo: dict = {}

    def iniciar(self, cfg: dict, modo: str) -> str | None:
        with self.lock:
            if self.status == "rodando":
                return "Já existe uma execução em andamento."
            if modo == "completo" and not garantir_chave_no_ambiente():
                return "Falta a GEMINI_API_KEY. O modo completo precisa dela (o demo não)."
            SAIDA.mkdir(exist_ok=True)
            CFG_EXEC.write_text(yaml.safe_dump(cfg, allow_unicode=True, sort_keys=False), encoding="utf-8")
            env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUNBUFFERED="1")
            cmd = [sys.executable, "-u", "-m", "videobot", "run", "--modo", modo, "--config", str(CFG_EXEC)]
            flags = subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == "win32" else 0
            self.proc = subprocess.Popen(cmd, cwd=RAIZ, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                         stdin=subprocess.DEVNULL, creationflags=flags)
            self.linhas = [f"$ python -m videobot run --modo {modo}  (formato {cfg.get('formato')}, "
                           f"tema: {(cfg.get('tema') or {}).get('tema_fixo') or 'pesquisa automática'})"]
            self.status, self.inicio, self.fim, self.resumo = "rodando", time.time(), 0.0, {}
            threading.Thread(target=self._ler, args=(self.proc,), daemon=True).start()
            return None

    def _ler(self, proc):
        for bruto in iter(proc.stdout.readline, b""):
            self.linhas.append(bruto.decode("utf-8", "replace").rstrip("\r\n"))
        rc = proc.wait()
        with self.lock:
            if self.status == "rodando":
                self.status = "ok" if rc == 0 else "erro"
            self.fim = time.time()
            if rc == 0:
                self.resumo = ler_json(SAIDA / "ultimo.json", {}) or {}
            self.linhas.append(f"(processo terminou com código {rc})")

    def parar(self):
        with self.lock:
            if not self.proc or self.status != "rodando":
                return
            self.status = "interrompido"
            if sys.platform == "win32":  # derruba também os processos de render e o Chromium
                subprocess.run(["taskkill", "/T", "/F", "/PID", str(self.proc.pid)], capture_output=True)
            else:
                self.proc.kill()

    def estado(self, desde: int) -> dict:
        return {"status": self.status, "linhas": self.linhas[desde:], "total": len(self.linhas),
                "segundos": round((self.fim or time.time()) - self.inicio, 1) if self.inicio else 0, "resumo": self.resumo}


EXEC = Execucao()


def listar_saidas() -> list[dict]:
    if not SAIDA.exists():
        return []
    out = []
    for p in sorted((d for d in SAIDA.iterdir() if d.is_dir() and not d.name.startswith("_")), key=lambda d: d.stat().st_mtime, reverse=True)[:12]:
        arqs = sorted(f.name for f in p.iterdir() if f.is_file() and not f.name.startswith("_"))
        out.append({"pasta": p.name, "arquivos": arqs})
    return out


# ---------------------------------------------------------------- HTTP
class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _json(self, obj, st=200):
        b = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(st)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(b)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(b)

    def _corpo(self) -> dict:
        n = int(self.headers.get("Content-Length") or 0)
        return json.loads(self.rfile.read(n) or b"{}") if n else {}

    def _mesma_origem(self) -> bool:
        org = self.headers.get("Origin")
        return not org or urlparse(org).hostname in ("127.0.0.1", "localhost")

    def do_GET(self):
        u = urlparse(self.path)
        q = parse_qs(u.query)
        if u.path == "/":
            b = PAGINA.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(b)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(b)
        elif u.path == "/api/config":
            self._json(estado_config())
        elif u.path == "/api/ambiente":
            self._json({"gemini": garantir_chave_no_ambiente(), "youtube": bool(os.environ.get("YOUTUBE_API_KEY", "").strip()),
                        "python": sys.version.split()[0], "raiz": str(RAIZ)})
        elif u.path == "/api/modelos":
            self._json(listar_modelos())
        elif u.path == "/api/estado":
            self._json(EXEC.estado(int((q.get("desde") or ["0"])[0])))
        elif u.path == "/api/saidas":
            self._json(listar_saidas())
        elif u.path.startswith("/saida/"):
            self._arquivo(unquote(u.path[len("/saida/"):]))
        elif u.path == "/fonte.ttf":
            b = (RAIZ / "fonts" / "figtree_Figtree-Variable.ttf").read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "font/ttf")
            self.send_header("Content-Length", str(len(b)))
            self.send_header("Cache-Control", "max-age=86400")
            self.end_headers()
            self.wfile.write(b)
        else:
            self._json({"erro": "não encontrado"}, 404)

    def _arquivo(self, rel: str):
        alvo = (SAIDA / rel).resolve()
        if SAIDA.resolve() not in alvo.parents or not alvo.is_file():
            return self._json({"erro": "arquivo não encontrado"}, 404)
        tipo = TIPOS_ARQUIVO.get(alvo.suffix.lower(), "application/octet-stream")
        tam = alvo.stat().st_size
        ini, fim = 0, tam - 1
        rng = re.match(r"bytes=(\d*)-(\d*)", self.headers.get("Range") or "")
        if rng and (rng.group(1) or rng.group(2)):
            if rng.group(1):
                ini = int(rng.group(1))
                fim = int(rng.group(2)) if rng.group(2) else tam - 1
            else:
                ini = max(0, tam - int(rng.group(2)))
            fim = min(fim, tam - 1)
            self.send_response(206)
            self.send_header("Content-Range", f"bytes {ini}-{fim}/{tam}")
        else:
            self.send_response(200)
        self.send_header("Content-Type", tipo)
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Length", str(fim - ini + 1))
        self.end_headers()
        try:
            with open(alvo, "rb") as f:
                f.seek(ini)
                falta = fim - ini + 1
                while falta > 0:
                    pedaco = f.read(min(1 << 20, falta))
                    if not pedaco:
                        break
                    self.wfile.write(pedaco)
                    falta -= len(pedaco)
        except (ConnectionResetError, BrokenPipeError, ConnectionAbortedError):
            pass

    def do_POST(self):
        if not self._mesma_origem():
            return self._json({"erro": "origem não permitida"}, 403)
        u = urlparse(self.path)
        try:
            corpo = self._corpo()
        except json.JSONDecodeError:
            return self._json({"erro": "JSON inválido"}, 400)
        if u.path == "/api/executar":
            modo = corpo.get("modo") if corpo.get("modo") in ("completo", "demo") else "completo"
            cfg = corpo.get("cfg") or estado_config()["efetivo"]
            erro = EXEC.iniciar(cfg, modo)
            self._json({"ok": not erro, "erro": erro})
        elif u.path == "/api/parar":
            EXEC.parar()
            self._json({"ok": True})
        elif u.path == "/api/config/salvar":
            base = yaml.safe_load((RAIZ / "config.yml").read_text(encoding="utf-8"))
            d = diferenca(base, corpo.get("cfg") or {})
            if d is _IGUAL:
                CONFIG_LOCAL.unlink(missing_ok=True)
            else:
                CONFIG_LOCAL.write_text("# Ajustes salvos pela interface local. Sobrepõem o config.yml só nesta máquina.\n"
                                        + yaml.safe_dump(d, allow_unicode=True, sort_keys=False), encoding="utf-8")
            self._json({"ok": True, "alteracoes": 0 if d is _IGUAL else len(json.dumps(d))})
        elif u.path == "/api/config/restaurar":
            CONFIG_LOCAL.unlink(missing_ok=True)
            self._json({"ok": True})
        elif u.path == "/api/abrir-pasta":
            alvo = (SAIDA / str(corpo.get("pasta", ""))).resolve()
            if alvo == SAIDA.resolve() or SAIDA.resolve() in alvo.parents:
                if sys.platform == "win32" and alvo.exists():
                    os.startfile(alvo)  # noqa: S606 — abre a pasta no Explorer
                self._json({"ok": True})
            else:
                self._json({"erro": "pasta inválida"}, 400)
        else:
            self._json({"erro": "não encontrado"}, 404)


def servir(porta: int = 8765, abrir: bool = True):
    garantir_chave_no_ambiente()
    srv = ThreadingHTTPServer(("127.0.0.1", porta), Handler)
    url = f"http://127.0.0.1:{porta}"
    print(f"Interface do vídeo diário em {url}  (Ctrl+C para fechar)", flush=True)
    if abrir:
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        EXEC.parar()
        srv.server_close()
