"""Linha de comando.

  python -m videobot run                         # usa config.yml
  python -m videobot run --modo demo             # testa motor/voz/render sem pesquisa nem LLM
  python -m videobot run --tema "chips de IA" --formato curto --duracao 60 --narracao gemini --voz Kore
  python -m videobot ui                          # interface local no navegador
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
    u = sub.add_parser("ui", help="abre a interface local no navegador")
    u.add_argument("--porta", type=int, default=8765)
    u.add_argument("--sem-navegador", action="store_true", help="não abre o navegador sozinho")
    a = ap.parse_args(argv)

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

    from .pipeline import executar
    executar(cfg, a.modo, a.refazer.strip())


if __name__ == "__main__":
    sys.exit(main())
