"""Catálogo do 3D temático: objetos desenhados em código (engine/tema3d.js) e a escolha por cena.

O roteirista (IA) marca em cada cena "objetos3d": 1 a 3 ids deste catálogo, o 1º é o principal.
Se ele não marcar (ou marcar algo que não existe), a escolha sai das palavras da cena e do tema.
"""
from __future__ import annotations

import re

from .util import sem_acento

# id: (descrição para o roteirista, palavras-chave em PT/EN sem acento)
CATALOGO: dict[str, tuple[str, tuple[str, ...]]] = {
    "foguete": ("foguete decolando com chama", ("foguete", "rocket", "lancamento", "lancar", "starship", "falcon", "spacex", "decol")),
    "satelite": ("satélite com painéis solares", ("satelite", "satellite", "starlink", "orbita", "constelacao")),
    "planeta": ("planeta com anel e órbita", ("marte", "mars", "planeta", "espaco", "space", "galaxia", "universo")),
    "lua": ("lua com crateras", ("lua", "lunar", "moon", "artemis")),
    "globo": ("globo terrestre com conexões entre países", ("mundo", "global", "pais", "paises", "internet", "world", "china", "eua", "europa", "geopolit", "exporta")),
    "chip": ("chip/processador com trilhas acesas", ("chip", "processador", "semicondutor", "tsmc", "silicio", "transistor", "nanometro")),
    "gpu": ("placa de vídeo (GPU) com ventoinhas", ("gpu", "nvidia", "placa de video", "h100", "b200", "blackwell", "cuda", "amd")),
    "servidor": ("rack de servidor com luzes", ("servidor", "server", "rack", "hardware", "computacao")),
    "datacenter": ("corredor de data center", ("data center", "datacenter", "centro de dados", "nuvem de dados", "hyperscale")),
    "robo": ("robô humanoide", ("robo", "robot", "humanoide", "automacao", "optimus", "android")),
    "rede_neural": ("rede neural com pulsos de dados", ("llm", "gpt", "chatgpt", "claude", "gemini", "neural", "treino", "treinamento", "aprendizado de maquina", "algoritmo", "modelo de ia", "modelos de ia", "agente")),
    "nuvem": ("nuvem de computação", ("nuvem", "cloud", "aws", "azure", "online", "software")),
    "celular": ("smartphone com tela acesa", ("celular", "smartphone", "iphone", "android", "app", "aplicativo", "telefone")),
    "notebook": ("notebook aberto", ("notebook", "laptop", "computador", "pc", "programador", "codigo", "programacao")),
    "moedas": ("pilha de moedas caindo", ("dinheiro", "us$", "r$", "dolar", "dolares", "reais", "euro", "receita", "lucro", "custo", "preco", "investimento", "investir", "investidor", "faturamento", "salario")),
    "grafico_alta": ("gráfico de barras subindo com seta", ("cresce", "crescimento", "alta", "subiu", "aumento", "dobrou", "recorde", "valoriza", "avaliacao", "ipo", "acoes", "mercado")),
    "grafico_queda": ("gráfico de barras caindo com seta", ("queda", "caiu", "cairam", "caem", "cair", "prejuizo", "perda", "despenca", "crise", "bolha", "recua", "deficit", "reduz", "encolhe")),
    "cidade": ("cidade/arranha-céus à noite", ("cidade", "predio", "urbano", "empresa", "empresas", "big tech", "sede", "metropole")),
    "fabrica": ("fábrica com chaminés", ("fabrica", "industria", "producao", "manufatura", "emissao", "poluicao", "carbono")),
    "usina": ("usina com torre de resfriamento", ("usina", "nuclear", "reator", "energia", "eletricidade", "rede eletrica", "gigawatt", "megawatt", "watt", "consumo")),
    "painel_solar": ("painéis solares", ("solar", "renovavel", "fotovolta", "sol")),
    "turbina_eolica": ("turbinas eólicas girando", ("eolica", "vento", "turbina", "limpa")),
    "bateria": ("bateria carregando", ("bateria", "battery", "carga", "litio", "armazenamento")),
    "raio": ("raio de energia", ("raio", "potencia", "eletric", "choque", "rapido", "velocidade")),
    "carro": ("carro elétrico", ("carro", "veiculo", "tesla", "autonomo", "transito", "motorista")),
    "drone": ("drone com hélices", ("drone", "militar", "defesa", "entrega", "vigilancia")),
    "cadeado": ("cadeado/segurança", ("seguranca", "privacidade", "hacker", "ataque", "senha", "criptografia", "golpe", "vazamento", "regulacao")),
    "documento": ("pilha de documentos/relatório", ("relatorio", "estudo", "pesquisa", "documento", "lei", "contrato", "paper", "artigo", "faa", "regra", "norma")),
    "lupa": ("lupa investigando", ("investiga", "analise", "verdade", "mito", "busca", "detalhe", "auditoria")),
    "relogio": ("relógio com ponteiros girando", ("tempo", "prazo", "anos", "minutos", "horas", "atraso", "futuro", "quando", "data")),
    "explosao": ("explosão/fogo", ("explosao", "explodiu", "fogo", "incendio", "falha", "destruido", "acidente")),
    "gota": ("gota d'água", ("agua", "resfriamento", "refrigeracao", "calor", "liquido", "litros")),
    "pessoas": ("grupo de pessoas", ("pessoas", "trabalhador", "emprego", "empregos", "usuario", "usuarios", "funcionario", "populacao", "humano", "demiss")),
    "predio_governo": ("prédio do governo com colunas", ("governo", "congresso", "lei", "estado", "senado", "regulador", "politica", "tribunal")),
    "balanca": ("balança (justiça/equilíbrio)", ("justica", "processo", "juiz", "equilibrio", "comparacao", "versus", "debate", "contra")),
}

CAMERAS = ("orbita", "aproxima", "sobe", "lateral")


def prompt_catalogo() -> str:
    itens = "; ".join(f"{k} ({d})" for k, (d, _) in CATALOGO.items())
    return ("CATÁLOGO 3D (campo \"objetos3d\" em cada cena: 1 a 3 ids, o 1º é o principal; escolha o que ilustra AQUELA cena, "
            "use SOMENTE os ids abaixo (os nomes de ICONE não valem aqui), "
            "ligado ao tema; varie o principal entre cenas seguidas): " + itens)


def _texto_cena(sc: dict) -> str:
    def junta(o):
        if isinstance(o, dict):
            return " ".join(junta(v) for k, v in o.items() if k not in ("icon", "tone", "kind"))
        if isinstance(o, list):
            return " ".join(junta(v) for v in o)
        return str(o) if isinstance(o, str) else ""
    return sem_acento((sc.get("text", "") + " " + junta(sc.get("params") or {})).lower())


def _pontua(txt: str) -> list[tuple[int, str]]:
    out = []
    for k, (_, palavras) in CATALOGO.items():
        n = sum(len(re.findall(r"(?<![a-z])" + re.escape(p), txt)) for p in palavras)
        if n:
            out.append((n, k))
    return sorted(out, key=lambda x: -x[0])


def escolher(sc: dict, tema: str, anterior: str = "") -> list[str]:
    """Objetos da cena, OBRIGATORIAMENTE ligados à fala dela.

    Só entra objeto cujas palavras-chave aparecem na narração ou na tela da cena: o que o roteirista
    marcou passa por esse filtro; sem marcação válida, vale o que a própria cena cita. O tema do
    vídeo não basta (era assim que um foguete aparecia em "36 milhões de empregos perdidos").
    Sem nenhum objeto ligado à fala, a cena fica sem objeto (lista vazia)."""
    ligados = [k for _, k in _pontua(_texto_cena(sc))]
    marcados = [str(x).strip().lower() for x in (sc.get("objetos3d") or [])]
    ids = [m for m in dict.fromkeys(marcados) if m in CATALOGO and m in ligados]
    ids += [k for k in ligados if k not in ids]
    if len(ids) > 1 and ids[0] == anterior:  # evita o mesmo objeto principal em cenas seguidas
        ids = ids[1:] + ids[:1]
    return ids[:3]


def _prompt_revisao(cenas: list[dict]) -> str:
    itens = "; ".join(f"{k} ({d})" for k, (d, _) in CATALOGO.items())
    linhas = "\n".join(f'- [{sc["id"]}] {sc["text"]}' for sc in cenas)
    return f"""Você é diretor de arte. Para cada cena, escolha de 0 a 2 objetos 3D do catálogo que mostram LITERALMENTE algo
que a frase daquela cena cita (o objeto, o lugar, a ação ou o dado dela). É OBRIGATÓRIO que o objeto tenha ligação direta com a
frase; ligação só com o tema geral do vídeo não serve. Na dúvida, não ponha objeto (lista vazia).
Exemplos: "a OpenAI vai gastar 1 trilhão em data centers" -> ["datacenter", "moedas"]; "36 milhões de empregos perdidos" ->
["pessoas", "grafico_queda"]; "o estudo de Harvard mostrou" -> ["documento"]; "você concorda?" -> [].

CATÁLOGO: {itens}

CENAS:
{linhas}

Responda SOMENTE com JSON: {{"cenas": [{{"id": "...", "objetos": ["id do catálogo"]}}]}}"""


def revisar(roteiro: dict, cfg: dict) -> int:
    """Revisão dedicada (uma chamada à IA): objetos ligados à fala de cada cena, ou nenhum.
    Cenas com foto/vídeo ficam de fora (a mídia cobre o 3D). Devolve quantas cenas foram revisadas."""
    from .llm import gerar_json
    cenas = [sc for ch in roteiro.get("chapters", []) for sc in ch.get("scenes", [])
             if not ((sc.get("params") or {}).get("_photo") or (sc.get("params") or {}).get("_video"))]
    if not cenas:
        return 0
    try:
        r, _, _ = gerar_json(_prompt_revisao(cenas), cfg, temperatura=0.1, max_tokens=2500)
    except Exception:
        return 0
    por_id = {str(c.get("id")): c for c in (r.get("cenas") or []) if isinstance(c, dict)}
    n = 0
    for sc in cenas:
        c = por_id.get(sc["id"])
        if c is None:
            continue
        sc["objetos_revisados"] = [str(o).strip().lower() for o in (c.get("objetos") or []) if str(o).strip().lower() in CATALOGO][:2]
        n += 1
    return n


def para_cenas(roteiro: dict) -> None:
    """Grava em cada cena params._3d = {objetos, camera} (usado pelo engine/tema3d.js).
    Usa a revisão dedicada quando existe; senão, só objetos cujas palavras aparecem na própria cena."""
    tema = roteiro.get("tema", "")
    anterior, i = "", 0
    for ch in roteiro.get("chapters", []):
        for sc in ch.get("scenes", []):
            prm = sc.get("params") or {}
            if prm.get("_photo") or prm.get("_video"):
                objs = []  # foto/vídeo cobrem a tela
            elif "objetos_revisados" in sc:
                objs = list(sc["objetos_revisados"])
            else:
                objs = escolher(sc, tema, anterior)
            cam = sc.get("camera3d") if sc.get("camera3d") in CAMERAS else CAMERAS[i % len(CAMERAS)]
            sc.setdefault("params", {})["_3d"] = {"objetos": objs, "camera": cam}
            anterior, i = (objs[0] if objs else ""), i + 1
