"""Publicação no YouTube e aprendizado com o Analytics (20/11/2026), sem rede (requests falso)."""
from __future__ import annotations

import json

from videobot import youtube


def test_sem_secrets_nao_publica(monkeypatch, cfg):
    monkeypatch.setattr(youtube, "chave", lambda n: None)
    assert youtube.publicar(cfg) is None


def test_metadados_do_pacote_e_rotulo_sintetico(tmp_path, cfg):
    pub = tmp_path / "publicacao.md"
    pub.write_text("### Descrição\n```\nLinha 1\nLinha 2\n```\n### Tags (2 tags)\n```\nIA, fibra óptica\n```\n", encoding="utf-8")
    import datetime as dt
    madrugada = dt.datetime(2026, 11, 21, 2, 15, tzinfo=dt.timezone(dt.timedelta(hours=-3)))
    m = youtube.metadados(pub, {"titulo": "Título X"}, cfg, agora=madrugada)
    assert m["snippet"]["title"] == "Título X" and m["snippet"]["description"] == "Linha 1\nLinha 2"
    assert m["snippet"]["tags"] == ["IA", "fibra óptica"] and m["status"]["containsSyntheticMedia"] is True
    # 21/11/2026: o canal passou a publicar público às 07:30 (antes o padrão era privado, revisado à mão)
    assert m["status"]["privacyStatus"] == "private" and m["status"]["publishAt"] == "2026-11-21T10:30:00Z"


def test_curto_usa_capa_vertical_e_longo_a_horizontal(tmp_path):
    """20/11/2026: o vídeo subiu sem capa. Agora: curto -> capa vertical; longo -> horizontal (1920x1080 se couber)."""
    capa = tmp_path / "capa_1080x1920.jpg"; capa.write_bytes(b"x")
    t720 = tmp_path / "thumb_1280x720.jpg"; t720.write_bytes(b"x")
    t1080 = tmp_path / "thumb_1920x1080.jpg"; t1080.write_bytes(b"x")
    assert youtube.escolher_thumb([str(t720), str(capa)], curto=True) == capa
    assert youtube.escolher_thumb([str(t720), str(t1080)], curto=False) == t1080
    assert youtube.escolher_thumb([str(t720)], curto=True) == t720, "sem capa vertical, o curto usa a horizontal"
    t1080.write_bytes(b"x" * (2 * 1024 * 1024 + 1))
    assert youtube.escolher_thumb([str(t1080), str(t720)], curto=False) == t720, "acima de 2 MB a API recusa"


def test_upload_guarda_id_no_historico(monkeypatch, tmp_path, cfg):
    from videobot import pipeline
    video = tmp_path / "x_curto.mp4"; video.write_bytes(b"mp4")
    (tmp_path / "saida").mkdir()
    (tmp_path / "saida" / "ultimo.json").write_text(json.dumps({"video": str(video), "titulo": "T", "thumbs": [], "publicacao": ""}), encoding="utf-8")
    monkeypatch.setattr(youtube, "RAIZ", tmp_path)
    monkeypatch.setattr(pipeline, "HIST", tmp_path / "temas.json")
    (tmp_path / "temas.json").write_text(json.dumps([{"slug": "x", "tema": "t"}]), encoding="utf-8")
    monkeypatch.setattr(youtube, "chave", lambda n: "v")
    enviado = {}

    class R:
        def __init__(self, st, js=None, hd=None): self.status_code, self._js, self.headers, self.text = st, js or {}, hd or {}, ""
        def json(self): return self._js
    monkeypatch.setattr(youtube.requests, "post", lambda url, **k: R(200, {"access_token": "a"}) if "oauth2" in url else
                        (enviado.update(meta=json.loads(k["data"])) or R(200, hd={"Location": "https://up"})))
    monkeypatch.setattr(youtube.requests, "put", lambda url, **k: R(200, {"id": "abc123"}))
    assert youtube.publicar(cfg) == "abc123"
    assert enviado["meta"]["status"]["containsSyntheticMedia"] is True
    assert json.loads((tmp_path / "temas.json").read_text(encoding="utf-8"))[0]["youtube"] == "abc123"


def test_licoes_do_canal_entram_no_roteiro(monkeypatch, tmp_path):
    d = {f"v{i}": {"views": 100, "averageViewPercentage": p, "titulo": f"T{i}", "gancho": f"g{i}"} for i, p in enumerate([80, 20, 60, 40])}
    (tmp_path / "d.json").write_text(json.dumps(d), encoding="utf-8")
    monkeypatch.setattr(youtube, "DESEMPENHO", tmp_path / "d.json")
    txt = youtube.licoes(1)
    assert "Mais retenção" in txt and '"T0"' in txt.split("Menos")[0] and '"T1"' in txt.split("Menos")[1]


def test_tags_coladas_com_espaco_viram_varias():
    """20/11/2026: a IA mandou as tags num texto só separado por espaços e o YouTube receberia 1 tag de 137 caracteres."""
    from videobot import publish
    tags = publish._tags_ok(["IA energia consumo data center GPT-3 GPT-4 eletricidade sustentabilidade tecnologia Brasil IA"])
    assert len(tags) >= 10 and "energia" in tags and tags.count("IA") == 1
    assert publish._tags_ok(["data center", "energia renovável"]) == ["data center", "energia renovável"]


def test_secrets_vao_para_o_github_pela_entrada_padrao(capsys):
    """youtube-auth grava as chaves com o gh: o valor nunca vai na linha de comando nem é impresso."""
    from videobot import youtube
    chamadas = []
    youtube.salvar_secrets_github({"YT_REFRESH_TOKEN": "segredo-123"}, run=lambda cmd, **k: chamadas.append((cmd, k)))
    cmd, k = chamadas[0]
    assert cmd == ["gh", "secret", "set", "YT_REFRESH_TOKEN", "--repo", "8saulo/video-diario-ia"]
    assert k["input"] == "segredo-123" and "segredo-123" not in " ".join(cmd)
    assert "segredo-123" not in capsys.readouterr().out


def test_cliente_digitado_sem_arquivo(monkeypatch):
    """Sem o client_secret.json, o Client ID e o Client secret são pedidos no terminal (o secret sem eco)."""
    import getpass
    from videobot import youtube
    monkeypatch.setattr("builtins.input", lambda *a: "123-abc.apps.googleusercontent.com")
    monkeypatch.setattr(getpass, "getpass", lambda *a: "GOCSPX-x")
    assert youtube._cliente("") == {"client_id": "123-abc.apps.googleusercontent.com", "client_secret": "GOCSPX-x"}


def test_cena_final_mostra_o_arroba_do_canal(cfg):
    from videobot import render
    fim = render.final_seguir(cfg, 0, False)
    assert {r["perfil"] for r in fim["redes"]} == {"@sauloconectati"}


def test_workflow_de_envio_avulso_usa_os_secrets_e_monta_o_ultimo_json():
    """publicar-youtube.yml: baixa o Release, monta saida/ultimo.json com os campos que publicar() lê e usa os 3 Secrets."""
    import yaml
    from videobot.util import RAIZ
    wf = yaml.safe_load((RAIZ / ".github" / "workflows" / "publicar-youtube.yml").read_text(encoding="utf-8"))
    passos = {p.get("name"): p for p in wf["jobs"]["publicar"]["steps"] if p.get("name")}
    env = passos["Publicar no YouTube"]["env"]
    assert set(env) == {"YT_CLIENT_ID", "YT_CLIENT_SECRET", "YT_REFRESH_TOKEN"}
    baixar = passos["Baixar o vídeo do Release"]["run"]
    for campo in ('"video"', '"thumbs"', '"publicacao"', '"titulo"'):
        assert campo in baixar


def test_chaves_gravadas_no_windows_sem_imprimir(capsys, monkeypatch):
    """youtube-auth --destino pc: grava em HKCU\Environment (como o setx), sem imprimir o valor, e o processo já enxerga."""
    import os
    from videobot import youtube
    gravados = {}

    class FakeReg:
        HKEY_CURRENT_USER, KEY_SET_VALUE, REG_SZ = "HKCU", 2, 1

        class OpenKey:
            def __init__(self, raiz, sub, *a):
                assert (raiz, sub) == ("HKCU", "Environment")
            def __enter__(self): return self
            def __exit__(self, *a): return False

        @staticmethod
        def SetValueEx(k, nome, _r, tipo, valor):
            gravados[nome] = valor

    monkeypatch.delenv("YT_REFRESH_TOKEN", raising=False)
    youtube.salvar_no_pc({"YT_REFRESH_TOKEN": "segredo-456"}, winreg_mod=FakeReg)
    assert gravados == {"YT_REFRESH_TOKEN": "segredo-456"} and os.environ["YT_REFRESH_TOKEN"] == "segredo-456"
    assert "segredo-456" not in capsys.readouterr().out


def test_publico_com_horario_agenda_para_as_7h30(cfg):
    """privacidade public + agendar_hora 07:30: sobe privado com publishAt às 07:30 de Brasília (10:30 UTC)."""
    import copy
    import datetime as dt
    from videobot import youtube
    c = copy.deepcopy(cfg)
    c.setdefault("entrega", {})["youtube"] = {"privacidade": "public", "agendar_hora": "07:30"}
    brt = dt.timezone(dt.timedelta(hours=-3))
    m = youtube.metadados(None, {"titulo": "t"}, c, agora=dt.datetime(2026, 11, 21, 2, 15, tzinfo=brt))
    assert m["status"]["privacyStatus"] == "private" and m["status"]["publishAt"] == "2026-11-21T10:30:00Z"


def test_publico_com_rotina_atrasada_publica_na_hora(cfg):
    """Se a rotina do GitHub atrasar e passar das 07:30, o vídeo sai público na hora, sem esperar o dia seguinte."""
    import copy
    import datetime as dt
    from videobot import youtube
    c = copy.deepcopy(cfg)
    c.setdefault("entrega", {})["youtube"] = {"privacidade": "public", "agendar_hora": "07:30"}
    brt = dt.timezone(dt.timedelta(hours=-3))
    m = youtube.metadados(None, {"titulo": "t"}, c, agora=dt.datetime(2026, 11, 21, 9, 40, tzinfo=brt))
    assert m["status"]["privacyStatus"] == "public" and "publishAt" not in m["status"]
