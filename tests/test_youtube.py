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
    m = youtube.metadados(pub, {"titulo": "Título X"}, cfg)
    assert m["snippet"]["title"] == "Título X" and m["snippet"]["description"] == "Linha 1\nLinha 2"
    assert m["snippet"]["tags"] == ["IA", "fibra óptica"] and m["status"]["containsSyntheticMedia"] is True
    assert m["status"]["privacyStatus"] == "private", "padrão seguro: você revisa antes de ficar público"


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
