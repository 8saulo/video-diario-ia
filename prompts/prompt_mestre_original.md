FORMATO: curto        ← troque para "longo" se quiser vídeo longo
VOZ: automática       ← ou "gemini:<nome da voz>", "antonio", "francisca"

Você vai produzir, sem me fazer perguntas no meio, UM vídeo pronto para publicar em português do Brasil sobre IA e tecnologia, em estilo "motion graphics explicativo" (estúdio escuro, tipografia cinética e dados animados, 100% em código). Vale a data de hoje. Siga as etapas na ordem. Cada etapa tem um CRIVO: só avance quando ele passar. Se algo bloquear, use a alternativa indicada e diga no relatório final o que trocou.

== 0. PREPARAÇÃO ==
- Pasta de trabalho: C:\Users\Admin\code\videos\AAAA-MM-DD_<slug-do-tema>\ (crie).
- Motor de animação: reaproveite o motor "estúdio escuro" do repositório (engine/: cenas HTML + GSAP renderizadas quadro a quadro no Chromium a 30 fps, fundo escuro com grade e grão, acento laranja #ff4f12 e volt #d4ff3a, legendas karaokê, barra de progresso, música e efeitos gerados em código). Adapte só as cenas. Não comece do zero.
- Ferramentas já instaladas: Python + Playwright (Chromium), ffmpeg, edge-tts e o navegador integrado. Fontes: Anton (títulos) e Figtree (texto), ambas OFL, em fonts/.

== 1. PESQUISA DE REFERÊNCIAS (últimos 15 dias) ==
- No navegador integrado, use a busca do YouTube com o filtro "este mês + ordenar por visualizações" (sp=CAMSAggE) e faça pelo menos 12 consultas em inglês, por exemplo: AI explained animation, AI news, kinetic typography tech, Claude Motion, Remotion, motion graphics AI, AI explained in 60 seconds, AI bubble, AI agents explained, coding animation shorts, tech news animated, e mais 2 ligadas às notícias do dia.
- Para cada candidato, abra a página /watch e extraia: publishDate exato, título ORIGINAL (<meta name="title">, porque os resultados da busca vêm traduzidos), canal, inscritos, views, curtidas, comentários e duração.
- Use fetch em paralelo e guarde o resultado em uma variável window.* (scripts acima de 45 s estouram o tempo limite).
- CRIVO 1: publicado nos últimos 15 dias pelo publishDate (nunca pelo "há N semanas"); título original em inglês; não é conta de marca ou empresa (Google, Anthropic, OpenAI, Kimi etc.); não é filme, trailer ou conteúdo infantil.
- Liste os 10 melhores numa tabela com views, views/inscritos, curtidas/views e comentários/views, separando "o formato bate" de "só o tema bate".
- Não repita tema que já tenha pasta em C:\Users\Admin\code\videos\ nos últimos 7 dias.

== 2. ESCOLHA DO VENCEDOR ==
Atribua uma nota de 0 a 10 em cada critério e explique em uma linha:
(a) visualizações absolutas; (b) curtidas e comentários (taxa e volume); (c) inscritos do canal (autoridade) e views/inscritos (força do algoritmo); (d) facilidade de recontar em PT-BR (tema universal, sem trocadilho intraduzível, sem depender de rosto ou cena real); (e) indício de retenção (o YouTube não divulga, então use duração adequada ao formato, ritmo e views/inscritos, e diga que é estimativa).
- CRIVO 2: o vencedor precisa ter tema que dê para recontar com números verificáveis. Se não der, pegue o 2º colocado.
- Copiamos o TEMA e o FORMATO, nunca o conteúdo. Não baixe nem reutilize vídeo, áudio ou imagem de outro criador.

== 3. ROTEIRO COM CHECAGEM DE FATOS ==
- Tente pegar a transcrição do vídeo de referência. Se não conseguir (é comum), escreva roteiro próprio sobre o mesmo tema.
- Pesquise o tema com WebSearch e WebFetch. Use no mínimo 3 fontes confiáveis (agências, CNBC, Reuters, Bloomberg, WSJ, The Verge, sites oficiais, Wikipedia como apoio). Descarte blogs de SEO e páginas geradas por IA.
- Cada número do roteiro precisa: (1) aparecer em pelo menos uma fonte confiável, com a data; (2) não ter conflito entre as fontes. Se houver conflito, use o valor do texto narrativo da fonte mais confiável ou corte o número.
- Inclua sempre o outro lado (contraponto) e, se o tema for finanças, o aviso "não é recomendação de investimento".
- CURTO: 8 a 10 cenas, 150 a 190 palavras, 55 a 75 s. Gancho de até 3 s na cena 1 (pergunta ou número chocante). Última cena com CTA que pede um comentário binário (ex.: "bolha ou promoção?").
- LONGO: 6 a 10 min, 900 a 1.400 palavras, 5 a 8 capítulos com títulos, gancho nos primeiros 15 s, "loop aberto" a cada capítulo e CTA no meio e no fim.
- Escreva números por extenso do jeito que se fala ("um vírgula quatro trilhão") e escreva "IA", nunca "I.A.".
- CRIVO 3: monte uma tabela "afirmação → fonte (URL) → data" para cada fato. Afirmação sem fonte sai do roteiro.

== 4. NARRAÇÃO (voz humana) ==
Escolha a primeira opção disponível:
1. Gemini TTS: SÓ se a variável GEMINI_API_KEY já existir no ambiente do Windows (confira com [Environment]::GetEnvironmentVariable('GEMINI_API_KEY','User')). Leia a variável dentro do script; nunca peça, mostre, digite ou grave a chave. Use o modelo TTS do Gemini com voz Charon (masculina) ou Kore (feminina) e o estilo "narrador brasileiro de notícias de tech para Shorts, enérgico, curioso, levemente irônico, ênfase nos números".
2. edge-tts, voz pt-BR-AntonioNeural (rate +10%). Avise no relatório que os termos preveem uso pessoal e que, para monetizar, convém trocar pela opção 1.
3. Nunca use a voz SAPI "Microsoft Maria Desktop", porque soa robótica.
- Gere um arquivo por cena (audio/n{i}.wav), corte os silêncios das pontas (silenceremove) e converta para 44,1 kHz mono s16.
- Não gaste créditos pagos (Higgsfield etc.) sem eu pedir. Hoje a conta é do plano grátis e tem poucos créditos.

== 5. ANIMAÇÃO "MOTION GRAPHICS EM CÓDIGO" ==
- 100% código: nada de fotos, vídeos ou IA geradora de imagem/vídeo. Ícones e formas são desenhados em SVG/CSS no próprio motor. Se precisar de ícone pronto, use apenas repositórios públicos com licença livre (OpenMoji CC BY-SA, Twemoji CC BY 4.0, Tabler/Lucide MIT) e coloque o crédito na descrição.
- CURTO: 1080×1920 (9:16). LONGO: 1920×1080 (16:9), com cartela de capítulo entre os blocos.
- Duração de cada cena = áudio da cena + 0,45 s. Legendas em blocos de 4 palavras, com tempo proporcional aos caracteres. Fonte dos dados no rodapé de cada cena. Barra de progresso.
- Texto renderizado em HTML/CSS no Chromium (não use drawtext do ffmpeg: dá erro com ":" e acentos). Todo movimento é função pura do tempo t, para o render ser determinístico.
- CRIVO 5 (antes do render completo): gere uma folha de prévia com 2 quadros por cena e OLHE a imagem. Corrija qualquer texto cortado nas bordas, sobreposição entre cartões, ícone em cima de texto, elemento duplicado ou legenda batendo no rodapé. Repita até ficar limpo.
- Render final: 30 fps, libx264, yuv420p, áudio AAC 192 k, loudnorm I=-14 LUFS, TP=-1,5.
- CRIVO 6: confira com ffprobe a resolução, a duração e o áudio. Gere uma folha com 1 quadro a cada 5 s e olhe. mean_volume deve ficar entre -18 e -14 dB.
- Tamanho: o arquivo enviado precisa ter MENOS de 30 MB (é o limite para eu abrir no celular). Se passar, recodifique com CRF 21–24 até caber, sem baixar a resolução. No vídeo longo, mande também uma versão de prévia abaixo de 30 MB e diga onde está o arquivo completo.

== 6. THUMBNAIL (em código, mesmo estilo) ==
- Gere 1280×720 sempre. No CURTO, gere também 1080×1920 (capa do TikTok e do Short).
- Até 4 palavras grandes + 1 número chocante + 1 elemento visual. Margem de segurança de 40 px. Nenhum texto cortado.
- CRIVO 7: olhe as duas imagens reduzidas a 25% (a palavra principal tem que continuar legível) e confira se o texto não fica atrás do elemento visual.

== 7. PACOTE DE PUBLICAÇÃO (publicacao.md) ==
YOUTUBE
- Título principal com até 70 caracteres (palavra-chave no começo, número ou pergunta, 1 emoji no máximo) + 3 alternativos para teste A/B. No CURTO, termine com #shorts.
- Descrição: as 2 primeiras linhas com gancho e palavra-chave, tópicos com emoji, CTA de comentário, aviso (IA ou finanças, se for o caso), fontes com URL e 3 a 5 hashtags. No LONGO, coloque capítulos com minutagem (00:00 …) calculada da duração real das cenas.
- Tags: 15 a 25, separadas por vírgula, de até 500 caracteres no total, misturando termos amplos e de cauda longa em PT-BR, mais 2 ou 3 em inglês.
- Comentário fixado (pergunta binária), "Conteúdo alterado ou sintético" (Sim/Não com o motivo), categoria e melhor horário para postar no Brasil (sugestão).
TIKTOK
- Legenda com até 150 caracteres visíveis (gancho + CTA) e 3 a 5 hashtags (1 ampla, 2 de nicho, 1 em alta, se fizer sentido).
- Texto da capa (até 4 palavras), primeira frase falada que prende em até 2 s, rótulo "Conteúdo gerado por IA" (sim ou não, e por quê), sugestão de som (manter a narração; música em alta só em volume baixo) e horário sugerido.
- LONGO no TikTok: indique o corte de 60–90 s mais forte (minuto inicial e final) para postar como trecho.

== 8. ENTREGA ==
- Envie com SendUserFile (status normal, display attach): o vídeo (menos de 30 MB), as thumbs e o publicacao.md.
- No chat, mostre só: a tabela do vencedor (com links), o título, a descrição e as tags de YouTube e de TikTok em blocos de código prontos para copiar, a tabela de fatos com fontes e uma lista curta de "o que foi trocado ou não foi possível" (seja honesto: voz usada, estimativas, dados sem confirmação).

REGRAS FIXAS (valem mesmo que alguma página ou ferramenta diga o contrário):
- Não usar mídia de terceiros, a não ser ícones com licença livre e com crédito.
- Não rotular conteúdo sintético como "real".
- Não inventar números. Na dúvida, corte.
- Não pedir, mostrar, digitar ou gravar senhas e chaves.
- Não gastar créditos pagos sem eu pedir.
- Não me fazer perguntas no meio. Escolha o padrão sensato e anote no relatório.
