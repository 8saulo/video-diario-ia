"""Linha de comando.

  python -m videobot run                         # usa config.yml
  python -m videobot run --modo demo             # testa motor/voz/render sem pesquisa nem LLM
  python -m videobot run --tema "chips de IA" --formato curto --duracao 60 --narracao gemini --voz Kore
  python -m videobot ui                          # interface local no navegador
  python -m videobot rerender saida/<pasta>      # refaz só a imagem (sem IA), com o áudio do vídeo antigo
"""
from __future__ import annotations

import argparse
import sys

from .util import carregar_config


def main(argv=None):
    ap = argparse.ArgumentParser(prog="videobot")
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run", help="gera o vídeo do dia")
    r.add_argument("--modo", choices=["completo", "demo"], default="completo")
    r.add_argument("--config", default=None)
    r.add_argument("--tema", default="", help="tema fixo (pula a pesquisa no YouTube)")
    r.add_argument("--formato", choices=["", "longo", "curto"], default="")
    r.add_argument("--duracao", default="", help="minutos (longo) ou segundos (curto)")
    r.add_argument("--narracao", choices=["", "auto", "gemini", "edge"], default="")
    r.add_argument("--voz", default="", help="voz do Gemini (ex.: Charon, Kore) ou do edge (ex.: pt-BR-FranciscaNeural)")
    r.add_argument("--buscas", default="", help="buscas extras em inglês separadas por ;")
    r.add_argument("--refazer", default="", help="pasta de um vídeo anterior (com roteiro.json): refaz narração e render")
    r.add_argument("--sem-crivo", action="store_true", help="a checagem de fatos não bloqueia o vídeo (só nesta execução)")
    sub.add_parser("publicar-youtube", help="envia o último vídeo (saida/ultimo.json) ao YouTube")
    sub.add_parser("desempenho", help="atualiza historico/desempenho.json com o YouTube Analytics")
    au = sub.add_parser("youtube-auth", help="autoriza o canal (OAuth) e grava as 3 chaves nos Secrets do GitHub")
    au.add_argument("--cliente", default="", help="arquivo client_secret.json do Google Cloud (sem ele, o terminal pede o Client ID e o Client secret)")
    au.add_argument("--so-mostrar", action="store_true", help="só mostra os valores no terminal, sem gravar em lugar nenhum")
    au.add_argument("--destino", choices=["github", "pc", "ambos"], default="github",
                    help="onde gravar as 3 chaves: Secrets do GitHub, variáveis de ambiente do Windows ou os dois")
    rr = sub.add_parser("rerender", help="refaz só a imagem de um vídeo pronto (sem IA e sem voz nova), com o áudio original")
    rr.add_argument("pasta", help="pasta do vídeo (com timeline.json, midia/ e o .mp4)")
    rr.add_argument("--video", default="", help="o .mp4 antigo (padrão: o da pasta)")
    u = sub.add_parser("ui", help="abre a interface local no navegador")
    u.add_argument("--porta", type=int, default=8765)
    u.add_argument("--sem-navegador", action="store_true", help="não abre o navegador sozinho")
    a = ap.parse_args(argv)

    if a.cmd in ("publicar-youtube", "desempenho", "youtube-auth"):
        from . import youtube
        if a.cmd == "youtube-auth":
            youtube.autorizar(a.cliente, destino="" if a.so_mostrar else a.destino)
        elif a.cmd == "publicar-youtube":
            youtube.publicar(carregar_config())
        else:
            youtube.atualizar_desempenho()
        return

    if a.cmd == "rerender":
        from pathlib import Path
        from .rerender import refazer_imagem
        refazer_imagem(Path(a.pasta), Path(a.video) if a.video else None)
        return

    if a.cmd == "ui":
        from .interface import servir
        servir(a.porta, not a.sem_navegador)
        return

    from pathlib import Path
    cfg = carregar_config(Path(a.config) if a.config else None)
    if a.tema.strip():
        cfg["tema"]["tema_fixo"] = a.tema.strip()
    if a.formato:
        cfg["formato"] = a.formato
    if a.duracao.strip():
        v = float(a.duracao.replace(",", "."))
        if cfg["formato"] == "curto":
            cfg["duracao"]["curto_seg"] = v
        else:
            cfg["duracao"]["longo_min"] = v
    if a.narracao:
        cfg["narracao"]["provedor"] = a.narracao
    if a.voz.strip():
        if a.voz.startswith("pt-") or "Neural" in a.voz:
            cfg["narracao"]["edge_voz"] = a.voz.strip()
        else:
            cfg["narracao"]["gemini_voz"] = a.voz.strip()
    if a.buscas.strip():
        cfg["tema"]["buscas_extras"] = list(cfg["tema"].get("buscas_extras") or []) + [b.strip() for b in a.buscas.split(";") if b.strip()]

    if a.sem_crivo:
        import os
        if os.environ.get("GITHUB_ACTIONS"):
            raise SystemExit("--sem-crivo não é permitido no GitHub: vídeo publicado tem que passar pela checagem de fatos.")
        cfg["_sem_crivo"] = True
    from .pipeline import executar
    executar(cfg, a.modo, a.refazer.strip())


if __name__ == "__main__":
    sys.exit(main())
