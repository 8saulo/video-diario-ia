"""Pauta do dia: tema escolhido com antecedência para uma data (config.yml → pautas).

  pautas:
    "2026-11-22":
      tema: "O IPO da Anthropic"
      formatos: [curto, longo]          # a rotina do dia faz os dois (um job do GitHub para cada)
      buscas_fatos: [...]               # buscas web garantidas na checagem de fatos
      angulo: "..."                     # ângulo do vídeo (vai para o roteiro)
      financas: true                    # roteiro inclui "não é recomendação de investimento"
      config: {...}                     # qualquer trecho do config.yml só para esse dia (voz, paleta, estilo do roteiro...)

Vale quando a execução não traz tema próprio (agendada, disparada pelo PC ou manual sem tema).
Este módulo só depende de PyYAML: o job "checar" do GitHub o usa antes de instalar o projeto.
"""
from __future__ import annotations

import argparse
import copy
import datetime as dt
import json
import sys
from pathlib import Path


def _merge(a: dict, b: dict) -> dict:
    out = copy.deepcopy(a)
    for k, v in (b or {}).items():
        out[k] = _merge(out[k], v) if isinstance(v, dict) and isinstance(out.get(k), dict) else copy.deepcopy(v)
    return out


def do_dia(cfg: dict, data: dt.date) -> dict | None:
    p = (cfg.get("pautas") or {}).get(data.isoformat())
    return p if isinstance(p, dict) and str(p.get("tema") or "").strip() else None


def aplicar(cfg: dict, data: dt.date) -> dict | None:
    """Põe a pauta da data em cfg (tema fixo, buscas, ângulo e os ajustes do dia). Devolve a pauta ou None."""
    p = do_dia(cfg, data)
    if not p:
        return None
    novo = _merge(cfg, p.get("config") or {})
    cfg.clear(); cfg.update(novo)
    t = cfg.setdefault("tema", {})
    t["tema_fixo"] = str(p["tema"]).strip()
    if p.get("buscas_fatos"):
        t["buscas_fatos"] = [str(b) for b in p["buscas_fatos"] if str(b).strip()]
    if p.get("angulo"):
        t["angulo"] = str(p["angulo"]).strip()
    if p.get("financas") is not None:
        t["financas"] = bool(p["financas"])
    return p


DIAS_SEMANA = {"segunda": 0, "terca": 1, "terça": 1, "quarta": 2, "quinta": 3, "sexta": 4, "sabado": 5, "sábado": 5, "domingo": 6}


def dia_do_longo(cfg: dict, data: dt.date) -> bool:
    """config.yml → longo_semanal: dia da semana em que a rotina também faz um vídeo longo ("" desliga)."""
    d = str(cfg.get("longo_semanal") or "").strip().lower().split("-")[0]
    return d in DIAS_SEMANA and data.weekday() == DIAS_SEMANA[d]


def formatos(cfg: dict, data: dt.date, evento: str = "schedule", formato_in: str = "", tema_in: str = "", refazer: str = "") -> list[str]:
    """Formatos que a rotina do dia gera. Com pauta (e sem tema/refazer pedidos na execução): os da pauta."""
    padrao = [formato_in or cfg.get("formato") or "curto"]
    if refazer.strip() or tema_in.strip():
        return padrao
    if evento != "schedule" and formato_in:  # disparo manual escolhendo o formato: só ele (ex.: refazer o longo que falhou)
        return padrao
    p = do_dia(cfg, data)
    if not p:
        base = [cfg.get("formato") or "curto"] if evento == "schedule" else padrao
        if not formato_in and dia_do_longo(cfg, data) and "longo" not in base:
            base.append("longo")  # um longo por semana, além do curto de todo dia
        return base
    fs = [f for f in (p.get("formatos") or []) if f in ("curto", "longo")]
    return list(dict.fromkeys(fs)) or padrao


def mesclar_temas(remoto: list, nosso: list, limite: int = 200) -> list:
    """Dois jobs do mesmo dia (curto e longo) gravam o histórico a partir do mesmo commit: junta sem perder entrada."""
    vistos = {json.dumps(e, sort_keys=True, ensure_ascii=False) for e in remoto}
    novos = [e for e in nosso if json.dumps(e, sort_keys=True, ensure_ascii=False) not in vistos]
    return sorted(list(remoto) + novos, key=lambda e: e.get("data", ""))[-limite:]


def mesclar_arquivos(raiz: Path, temas_nosso: Path, desempenho_nosso: Path | None = None) -> None:
    """Depois de 'git reset --hard origin/main': repõe o que este job acrescentou ao histórico."""
    alvo = raiz / "historico" / "temas.json"
    remoto = json.loads(alvo.read_text(encoding="utf-8")) if alvo.exists() else []
    nosso = json.loads(temas_nosso.read_text(encoding="utf-8")) if temas_nosso.exists() else []
    alvo.write_text(json.dumps(mesclar_temas(remoto, nosso), ensure_ascii=False, indent=2), encoding="utf-8")
    if desempenho_nosso and desempenho_nosso.exists():
        d = json.loads(desempenho_nosso.read_text(encoding="utf-8") or "{}")
        if d:  # retrato mais novo do YouTube Analytics
            (raiz / "historico" / "desempenho.json").write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")


def hoje_brasilia() -> dt.date:
    from zoneinfo import ZoneInfo
    return dt.datetime.now(ZoneInfo("America/Sao_Paulo")).date()


def main(argv=None):
    import yaml
    ap = argparse.ArgumentParser(prog="videobot.pauta")
    ap.add_argument("--config", default=str(Path(__file__).resolve().parents[1] / "config.yml"))
    ap.add_argument("--data", default="")
    ap.add_argument("--evento", default="schedule")
    ap.add_argument("--formato", default="")
    ap.add_argument("--tema", default="")
    ap.add_argument("--refazer", default="")
    ap.add_argument("--mesclar", nargs="+", metavar="ARQ", help="temas.json [desempenho.json] deste job, para juntar ao histórico atual")
    a = ap.parse_args(argv)
    if a.mesclar:
        raiz = Path(a.config).resolve().parent
        mesclar_arquivos(raiz, Path(a.mesclar[0]), Path(a.mesclar[1]) if len(a.mesclar) > 1 else None)
        return
    cfg = yaml.safe_load(Path(a.config).read_text(encoding="utf-8"))
    data = dt.date.fromisoformat(a.data) if a.data else hoje_brasilia()
    print(json.dumps(formatos(cfg, data, a.evento, a.formato, a.tema, a.refazer)))


if __name__ == "__main__":
    sys.exit(main())
