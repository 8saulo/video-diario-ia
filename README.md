# video-diario-ia

Gera **todo dia, sozinho, no GitHub Actions** um vídeo em português sobre IA e tecnologia, pronto para publicar:

1. **Pesquisa** no YouTube os vídeos em inglês que mais cresceram nos últimos 15 dias (≥ 12 buscas), aplica o CRIVO 1 (sem marcas, filmes ou conteúdo infantil, só título em inglês) e veta temas usados nos últimos 7 dias.
2. **Escolhe** o vencedor pelas notas (a) views, (b) curtidas/comentários, (c) inscritos e views/inscritos, (d) facilidade de recontar e (e) retenção estimada.
3. **Checa fatos**: busca fontes na web pela API do Tavily (ou da Wikipedia), **baixa cada página**, uma IA grátis (Groq ou OpenRouter) extrai os números só do texto baixado e o script confere se cada número está mesmo na página. Se não estiver, o fato é cortado.
4. **Escreve o roteiro** só com números confirmados e valida tudo em código: palavras, capítulos, números por extenso, "IA" e números na tela iguais aos das fontes.
5. **Narra** com a voz do Google AI Studio (Gemini TTS). Só se ela não conseguir gerar, refaz tudo com edge-tts, sem misturar vozes.
6. **Anima** em código no estilo "estúdio escuro": cenas HTML + GSAP renderizadas quadro a quadro no Chromium, a 30 fps.
   - Tipos de cena: número gigante, comparação, lista, barras, citação, linha do tempo, KPIs, chat de IA, ícones, pergunta, medidor, fluxo e CTA.
   - Legendas karaokê, cartelas de capítulo, fonte no rodapé e barra de progresso.
7. **Confere** o resultado:
   - prévia de layout (CRIVO 5);
   - ffprobe, folha de quadros e volume entre −18 e −14 dB, com loudnorm a −14 LUFS (CRIVO 6);
   - thumb 1280×720, mais capa 1080×1920 no curto, com margem de 40 px e teste a 25% (CRIVO 7).
8. **Entrega** um *Release* no GitHub com o vídeo, uma prévia de até 30 MB que abre no celular, as thumbs, o `publicacao.md` (YouTube + TikTok), o `pesquisa.md` e o `fatos.md`.

O visual segue a linguagem do [editonny](https://github.com/soumatheusgomes/editonny) (tokens de cor e tipografia do `DESIGN.md`, MIT). Nenhuma mídia de terceiros é usada: ícones, trilha e efeitos são gerados em código.

---

## Configurar (uma vez)

No GitHub, abra **Settings → Secrets and variables → Actions → New repository secret** e crie:

| Secret | Obrigatória? | Para quê | Onde pegar |
|---|---|---|---|
| `GROQ_API_KEY` | Pelo menos **uma** das duas de texto | Triagem, extração de fatos e roteiro (1ª opção) | [console.groq.com/keys](https://console.groq.com/keys) |
| `OPENROUTER_API_KEY` | ↑ | Texto (2ª opção, quando o Groq esgota; só modelos `:free`) | [openrouter.ai/keys](https://openrouter.ai/keys) |
| `TAVILY_API_KEY` | **Recomendada** | Busca de fontes e notícias na web. Sem ela, sobra a Wikipedia (sem notícias recentes) | [tavily.com](https://tavily.com) |
| `GEMINI_API_KEY` | Não | Só a narração (Gemini TTS). Sem ela, a voz sai no edge-tts | [aistudio.google.com/apikey](https://aistudio.google.com/apikey) |
| `YOUTUBE_API_KEY` | Não, mas recomendada | Pesquisa no YouTube mais confiável. Sem ela, o script lê as páginas públicas | Google Cloud Console → ative "YouTube Data API v3" → Credenciais → Chave de API |

Sem nenhuma chave de texto, a execução diária para com um aviso claro. O **modo demo** funciona sem nenhuma chave: ele usa um roteiro fixo e serve para testar o motor.

Os planos grátis têm limites por minuto e por dia. O script tenta os provedores na ordem de `llm.ordem` e, dentro de cada um, os modelos da sua chave (preferidos primeiro). Quando um estoura a cota, passa para o próximo. Quanto mais chaves, menos chance de o dia ficar sem IA.

> As chaves ficam só nas secrets do GitHub (ou nas variáveis do seu PC). O código lê a chave do ambiente, envia só no cabeçalho da requisição e nunca a imprime.

## Rodar e personalizar

- **Automático**: todo dia às **06:17 de Brasília**. Para mudar, edite a linha `cron` em [`.github/workflows/video-diario.yml`](.github/workflows/video-diario.yml). O horário é em UTC; Brasília é UTC−3.
- **Na hora, com opções**: **Actions → Vídeo diário → Run workflow**.

| Campo | O que faz |
|---|---|
| `modo` | `completo` (pesquisa + roteiro + vídeo) ou `demo` (testa motor, voz e render) |
| `tema` | Tema fixo; pula a pesquisa. Ex.: `chips de IA da Nvidia` |
| `formato` | `longo` (16:9, 6–10 min, capítulos) ou `curto` (9:16, 55–75 s) |
| `duracao` | Minutos (longo) ou segundos (curto) |
| `narracao` | `auto` (Google AI Studio e, se falhar, edge-tts), `gemini` ou `edge` |
| `voz` | Gemini: `Charon`, `Kore`, `Puck`, `Fenrir`, `Aoede`, `Orus`… · edge: `pt-BR-AntonioNeural`, `pt-BR-FranciscaNeural` |
| `buscas` | Buscas extras em inglês, separadas por `;` |

Os padrões ficam no [`config.yml`](config.yml):
- nicho, lista de buscas, janela de dias, veto de repetição e temas de reserva;
- formato e duração;
- voz e modelos preferidos;
- cores de destaque, marca d'água, legendas, música e efeitos;
- modelos de texto e número mínimo de fontes.

### Rodar em outra máquina

Precisa de Python 3.10+ e ffmpeg.

```bash
pip install -r requirements.txt
```

```bash
python -m playwright install --with-deps chromium
```

```bash
python -m videobot run --modo demo
```

Com pelo menos uma chave de texto (ex.: `GROQ_API_KEY`) definida no ambiente:

```bash
python -m videobot run --tema "robôs humanoides" --formato curto --duracao 60 --voz Kore
```

O resultado vai para `saida/AAAA-MM-DD_tema/`.

### Interface local (navegador)

```bash
python -m videobot ui
```

No Windows, também dá para dar duplo clique em `Abrir interface.bat`. Abre `http://127.0.0.1:8765`, que só fica acessível nesta máquina.

- **Novo vídeo:** modo (completo/demo), formato e duração, pesquisa automática ou assunto manual, voz e modelos de cada provedor de texto e do Gemini TTS (lista os disponíveis para as suas chaves).
- **Todas as configurações:** cada variável do `config.yml` com a explicação do próprio arquivo. "Salvar como padrão" grava só o que mudou em `config.local.yml` (fora do git), que também vale para o comando no terminal.
- **Execução:** passo a passo das etapas, progresso do render e o terminal ao vivo; no fim, o vídeo e os arquivos.
- A chave é lida do ambiente ou, no Windows, das variáveis da conta (`setx`) e nunca vai para o navegador.

## Regras fixas (valem sempre)

- Não usar mídia de terceiros. Exceção: fontes tipográficas OFL, com crédito em [CREDITS.md](CREDITS.md).
- Não rotular conteúdo sintético como "real". O pacote já marca o rótulo de IA no TikTok por causa da voz sintética.
- Não inventar números: fato cuja página não confirma o número é cortado.
- Não pedir, mostrar, digitar ou gravar chaves.
- Não gastar créditos pagos. Só usa o plano grátis do Google AI Studio.
- Copiar o TEMA e o FORMATO das referências, nunca o conteúdo. Nada é baixado de outros criadores.

## Limitações conhecidas

- **Cota grátis do Gemini TTS** é pequena. O script faz o mínimo de pedidos (um por capítulo) e descobre sozinho os modelos TTS disponíveis para a chave. Se todos derem 429, a narração sai em edge-tts. Os termos do edge-tts preveem uso pessoal; para monetizar, use o Gemini com cota.
- **GitHub desativa agendamentos** de repositórios públicos após 60 dias sem atividade. O commit diário do histórico deve contar como atividade; se mesmo assim for desativado, reative em *Actions*.
- A pesquisa sem `YOUTUBE_API_KEY` depende das páginas públicas do YouTube, que às vezes bloqueiam servidores. Nesse caso, usa os temas de reserva.
- A nota (e) de retenção é sempre estimativa: o YouTube não divulga retenção de vídeos de terceiros.

## Estrutura

| Caminho | Função |
|---|---|
| `videobot/research.py` | Pesquisa no YouTube, CRIVO 1, notas e vencedor |
| `videobot/llm.py` | Cliente de texto: Groq → OpenRouter (Gemini opcional) |
| `videobot/busca.py` | Busca na web por API: Tavily → Wikipedia |
| `videobot/facts.py` | Fatos extraídos das páginas baixadas e conferidos nelas |
| `videobot/script.py` | Roteiro, cenas e pacote de publicação validados |
| `videobot/tts.py` | Gemini TTS → edge-tts, alinhamento palavra a palavra (faster-whisper) |
| `videobot/audio.py` | Trilha e efeitos sintetizados, ducking, loudnorm |
| `videobot/render.py` | Render determinístico em paralelo, CRIVOs 5, 6 e 7, thumbs |
| `videobot/publish.py` | `publicacao.md` e relatório |
| `engine/` | Motor visual (HTML/CSS/GSAP) e ícones desenhados para o projeto |
| `exemplos/demo.json` | Roteiro de demonstração |
| `historico/temas.json` | Temas já usados (para o veto de 7 dias) |
| `prompts/prompt_mestre_original.md` | Prompt original que este pipeline automatiza |
