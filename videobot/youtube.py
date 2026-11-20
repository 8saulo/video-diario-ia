"""Publicação no YouTube (API oficial) e aprendizado com o YouTube Analytics.

Autorização (OAuth, uma vez só): `python -m videobot youtube-auth --cliente client_secret.json` no seu PC abre o login do
Google e mostra o refresh token. No GitHub: Secrets YT_CLIENT_ID, YT_CLIENT_SECRET e YT_REFRESH_TOKEN. Sem eles, nada é
publicado (o vídeo continua no Release). As chaves nunca são impressas pelo pipeline.

- publicar(): upload resumível do vídeo + metadados (título, descrição, tags, categoria, idioma, rótulo de conteúdo sintético)
  e thumb; privacidade em entrega.youtube.privacidade (private | unlisted | public) e agendamento opcional.
- atualizar_desempenho(): lê do Analytics visualizações, retenção média, duração média e inscritos dos vídeos publicados e grava
  historico/desempenho.json.
- licoes(): resume o que funcionou e o que não funcionou (por retenção), para entrar no prompt do roteiro.
"""
from __future__ import annotations

import datetime as dt
import json
import os
from pathlib import Path

import requests

from .util import RAIZ, chave, escrever_json, ler_json, log, nota

TOKEN_URL = "https://oauth2.googleapis.com/token"
ESCOPOS = ["https://www.googleapis.com/auth/youtube.upload", "https://www.googleapis.com/auth/youtube.readonly",
           "https://www.googleapis.com/auth/yt-analytics.readonly"]
DESEMPENHO = RAIZ / "historico" / "desempenho.json"


def configurado() -> bool:
    return all(chave(n) for n in ("YT_CLIENT_ID", "YT_CLIENT_SECRET", "YT_REFRESH_TOKEN"))


def _token() -> str:
    r = requests.post(TOKEN_URL, data={"client_id": chave("YT_CLIENT_ID"), "client_secret": chave("YT_CLIENT_SECRET"),
                                       "refresh_token": chave("YT_REFRESH_TOKEN"), "grant_type": "refresh_token"}, timeout=30)
    if r.status_code != 200:
        raise RuntimeError(f"o Google recusou a autorização (HTTP {r.status_code}); refaça o youtube-auth")
    return r.json()["access_token"]


def metadados(pub_md: Path | None, ultimo: dict, cfg: dict) -> dict:
    """Título, descrição e tags a partir do pacote de publicação do vídeo (publicacao.md)."""
    ycfg = (cfg.get("entrega") or {}).get("youtube") or {}
    texto = pub_md.read_text(encoding="utf-8") if pub_md and pub_md.is_file() else ""

    def bloco(titulo: str) -> str:
        i = texto.find(titulo)
        if i < 0:
            return ""
        a = texto.find("```", i)
        b = texto.find("```", a + 3)
        return texto[a + 3:b].strip() if a >= 0 and b > a else ""
    desc = bloco("### Descrição")
    tags = [t.strip() for t in bloco("### Tags").split(",") if t.strip()]
    status = {"privacyStatus": ycfg.get("privacidade", "private"), "selfDeclaredMadeForKids": False,
              "containsSyntheticMedia": True}  # narração com voz sintética: o YouTube pede esse rótulo
    agendar = str(ycfg.get("agendar_hora") or "").strip()
    if agendar and status["privacyStatus"] == "private":
        h, m = (agendar.split(":") + ["0"])[:2]
        quando = dt.datetime.now(dt.timezone(dt.timedelta(hours=-3))).replace(hour=int(h), minute=int(m), second=0, microsecond=0)
        if quando < dt.datetime.now(quando.tzinfo) + dt.timedelta(minutes=20):
            quando += dt.timedelta(days=1)
        status["publishAt"] = quando.astimezone(dt.timezone.utc).isoformat().replace("+00:00", "Z")
    return {"snippet": {"title": (ultimo.get("titulo") or "Vídeo")[:100], "description": desc[:4900], "tags": tags[:30],
                        "categoryId": str(ycfg.get("categoria_id", "28")), "defaultLanguage": "pt-BR", "defaultAudioLanguage": "pt-BR"},
            "status": status}


def publicar(cfg: dict) -> str | None:
    """Envia o vídeo de saida/ultimo.json. Devolve o id do vídeo no YouTube ou None."""
    if not ((cfg.get("entrega") or {}).get("youtube") or {}).get("ativo", True):
        return None
    if not configurado():
        nota("YouTube: sem YT_CLIENT_ID/YT_CLIENT_SECRET/YT_REFRESH_TOKEN; o vídeo ficou só no Release.")
        return None
    ultimo = ler_json(RAIZ / "saida" / "ultimo.json", {})
    video = Path(ultimo.get("video", ""))
    if not video.exists():
        raise RuntimeError("não achei o vídeo de saida/ultimo.json")
    meta = metadados(Path(ultimo.get("publicacao", "")), ultimo, cfg)
    tk = _token()
    h = {"Authorization": f"Bearer {tk}"}
    r = requests.post("https://www.googleapis.com/upload/youtube/v3/videos?uploadType=resumable&part=snippet,status",
                      headers={**h, "Content-Type": "application/json; charset=UTF-8", "X-Upload-Content-Type": "video/mp4",
                               "X-Upload-Content-Length": str(video.stat().st_size)}, data=json.dumps(meta), timeout=60)
    if r.status_code != 200:
        raise RuntimeError(f"YouTube recusou o envio (HTTP {r.status_code}): {r.text[:200]}")
    destino = r.headers["Location"]
    with open(video, "rb") as f:
        r = requests.put(destino, headers={**h, "Content-Type": "video/mp4"}, data=f, timeout=3600)
    if r.status_code not in (200, 201):
        raise RuntimeError(f"upload falhou (HTTP {r.status_code}): {r.text[:200]}")
    vid = r.json()["id"]
    thumbs = [Path(t) for t in ultimo.get("thumbs", []) if Path(t).exists()]
    thumb = next((t for t in thumbs if "1920" in t.name), thumbs[0] if thumbs else None)
    if thumb and "capa_" not in thumb.name:
        rt = requests.post(f"https://www.googleapis.com/upload/youtube/v3/thumbnails/set?videoId={vid}",
                           headers={**h, "Content-Type": "image/jpeg"}, data=thumb.read_bytes(), timeout=120)
        if rt.status_code != 200:  # thumb personalizada exige canal verificado por telefone
            nota(f"YouTube: thumb não aplicada (HTTP {rt.status_code}); verifique o canal em youtube.com/verify.")
    log(f"YouTube: enviado como {meta['status']['privacyStatus']} -> https://youtu.be/{vid}")
    # guarda o id no histórico (para o Analytics saber de qual vídeo é cada número)
    from .pipeline import HIST
    hist = ler_json(HIST, []) or []
    for e in reversed(hist):
        if e.get("slug") and e["slug"] in str(video):
            e["youtube"] = vid
            e["titulo"] = meta["snippet"]["title"]
            break
    escrever_json(HIST, hist)
    return vid


def atualizar_desempenho(dias: int = 28) -> int:
    """Lê do YouTube Analytics os números dos vídeos publicados e grava historico/desempenho.json."""
    if not configurado():
        return 0
    from .pipeline import HIST
    hist = [e for e in (ler_json(HIST, []) or []) if e.get("youtube")]
    if not hist:
        return 0
    tk = _token()
    fim = dt.date.today()
    ini = fim - dt.timedelta(days=max(dias, 3))
    dados = ler_json(DESEMPENHO, {}) or {}
    for i in range(0, len(hist), 40):
        lote = hist[i:i + 40]
        r = requests.get("https://youtubeanalytics.googleapis.com/v2/reports", headers={"Authorization": f"Bearer {tk}"}, params={
            "ids": "channel==MINE", "startDate": ini.isoformat(), "endDate": fim.isoformat(), "dimensions": "video",
            "metrics": "views,averageViewDuration,averageViewPercentage,likes,subscribersGained",
            "filters": "video==" + ",".join(e["youtube"] for e in lote)}, timeout=60)
        if r.status_code != 200:
            nota(f"YouTube Analytics: HTTP {r.status_code} ({r.text[:120]})")
            break
        cols = [c["name"] for c in r.json().get("columnHeaders", [])]
        for linha in r.json().get("rows", []) or []:
            d = dict(zip(cols, linha))
            e = next((x for x in lote if x["youtube"] == d["video"]), {})
            dados[d["video"]] = {**d, "tema": e.get("tema", ""), "titulo": e.get("titulo", ""), "data": e.get("data", ""),
                                 "gancho": e.get("gancho", ""), "atualizado": fim.isoformat()}
    escrever_json(DESEMPENHO, dados)
    log(f"YouTube Analytics: {len(dados)} vídeo(s) com números")
    return len(dados)


def licoes(n: int = 3) -> str:
    """O que funcionou e o que não funcionou no canal (retenção média), para o roteirista aprender."""
    dados = [d for d in (ler_json(DESEMPENHO, {}) or {}).values() if (d.get("views") or 0) >= 30]
    if len(dados) < 4:
        return ""
    dados.sort(key=lambda d: d.get("averageViewPercentage") or 0, reverse=True)
    fmt = lambda d: f'- "{d.get("titulo") or d.get("tema")}" (gancho: "{d.get("gancho", "")}"): retenção {d.get("averageViewPercentage", 0):.0f}%, {d.get("views")} views'
    return ("O QUE O PÚBLICO DO CANAL MOSTROU (YouTube Analytics, use como aprendizado; não copie temas):\n"
            "Mais retenção:\n" + "\n".join(fmt(d) for d in dados[:n]) +
            "\nMenos retenção:\n" + "\n".join(fmt(d) for d in dados[-n:]) +
            "\nRepita o que os de mais retenção têm em comum (gancho, ritmo, tipo de revelação) e evite o padrão dos de menos.")


REPO = "8saulo/video-diario-ia"


def salvar_secrets_github(valores: dict, repo: str = REPO, run=None) -> None:
    """Grava cada valor como Secret do repositório com o gh CLI. O valor vai pela entrada padrão (nunca na linha de
    comando, que fica no histórico/lista de processos) e nada é impresso além do nome do Secret."""
    import subprocess
    run = run or subprocess.run
    for nome, valor in valores.items():
        run(["gh", "secret", "set", nome, "--repo", repo], input=valor, text=True, check=True, capture_output=True)
        print(f"  Secret {nome} gravado no GitHub")


def salvar_no_pc(valores: dict, winreg_mod=None) -> None:
    """Grava cada valor como variável de ambiente da conta do Windows (HKCU\\Environment, o mesmo lugar do `setx`),
    sem passar pela linha de comando e sem imprimir. util.chave() lê de lá mesmo em terminais já abertos."""
    import os
    if winreg_mod is None:
        import winreg as winreg_mod
    with winreg_mod.OpenKey(winreg_mod.HKEY_CURRENT_USER, "Environment", 0, winreg_mod.KEY_SET_VALUE) as k:
        for nome, valor in valores.items():
            winreg_mod.SetValueEx(k, nome, 0, winreg_mod.REG_SZ, valor)
            os.environ[nome] = valor
            print(f"  {nome} gravado nas variáveis de ambiente do Windows")


def _cliente(cliente_json: str) -> dict:
    """client_id/client_secret: do client_secret.json ou digitados no terminal (o secret sem eco na tela)."""
    if cliente_json:
        c = json.loads(Path(cliente_json).read_text(encoding="utf-8"))
        return c.get("installed") or c.get("web") or c
    import getpass
    cid = input("Client ID (termina em .apps.googleusercontent.com): ").strip()
    sec = getpass.getpass("Client secret (não aparece enquanto digita): ").strip()
    if not cid.endswith(".apps.googleusercontent.com") or not sec:
        raise SystemExit("Client ID ou Client secret inválido.")
    return {"client_id": cid, "client_secret": sec}


def autorizar(cliente_json: str = "", destino: str = "github") -> None:
    """Fluxo OAuth local (loopback): abre o login do Google e grava YT_CLIENT_ID, YT_CLIENT_SECRET e YT_REFRESH_TOKEN
    direto nos Secrets do GitHub (gh CLI). Com salvar_github=False, mostra os valores só no SEU terminal."""
    import http.server
    import secrets
    import threading
    import urllib.parse
    import webbrowser
    c = _cliente(cliente_json)
    estado, porta, codigo = secrets.token_urlsafe(16), 8765 + 2, {}

    class H(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            if q.get("state", [""])[0] == estado:
                codigo["c"] = q.get("code", [""])[0]
            self.send_response(200); self.end_headers()
            self.wfile.write("Pronto! Pode fechar esta aba e voltar ao terminal.".encode("utf-8"))

        def log_message(self, *a):
            pass
    srv = http.server.HTTPServer(("127.0.0.1", porta), H)
    threading.Thread(target=srv.handle_request, daemon=True).start()
    redir = f"http://127.0.0.1:{porta}"
    url = "https://accounts.google.com/o/oauth2/v2/auth?" + urllib.parse.urlencode({
        "client_id": c["client_id"], "redirect_uri": redir, "response_type": "code", "scope": " ".join(ESCOPOS),
        "access_type": "offline", "prompt": "consent", "state": estado})
    print("Abrindo o login do Google no navegador...")
    webbrowser.open(url)
    srv.timeout = 300
    while "c" not in codigo:
        srv.handle_request()
    r = requests.post(TOKEN_URL, data={"code": codigo["c"], "client_id": c["client_id"], "client_secret": c["client_secret"],
                                       "redirect_uri": redir, "grant_type": "authorization_code"}, timeout=30)
    r.raise_for_status()
    rt = r.json().get("refresh_token")
    if not rt:
        raise SystemExit("O Google não devolveu o refresh token; tente de novo (o login precisa mostrar a tela de permissões).")
    valores = {"YT_CLIENT_ID": c["client_id"], "YT_CLIENT_SECRET": c["client_secret"], "YT_REFRESH_TOKEN": rt}
    ok = bool(destino)
    if destino in ("pc", "ambos"):
        try:
            salvar_no_pc(valores)
        except Exception as e:
            ok = False
            print(f"\nNão consegui gravar no Windows ({type(e).__name__}).")
    if destino in ("github", "ambos"):
        try:
            salvar_secrets_github(valores)
        except Exception as e:
            ok = False
            print(f"\nNão consegui gravar no GitHub com o gh ({type(e).__name__}).")
    if ok:
        print("Pronto! " + {"github": "A próxima execução no GitHub já publica no YouTube.",
                            "pc": "O PC já pode publicar (python -m videobot publicar-youtube).",
                            "ambos": "GitHub e PC já podem publicar no YouTube."}[destino])
        return
    print("\nSalve estes 3 valores como Secrets do repositório no GitHub (Settings > Secrets and variables > Actions):")
    print("  YT_CLIENT_ID     =", c["client_id"])
    print("  YT_CLIENT_SECRET = (o client_secret do arquivo JSON)")
    print("  YT_REFRESH_TOKEN =", rt)
    print("Depois apague este terminal/histórico. Não compartilhe o refresh token com ninguém.")
