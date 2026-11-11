# Instruções para agentes (Claude, Codex etc.)

## Regra obrigatória: teste de regressão a cada alteração

Toda alteração de código (correção de bug, recurso novo ou mudança de comportamento) vem
acompanhada de pelo menos um teste em `tests/` que:

- **reproduz o problema corrigido** (falharia no código antigo) ou **fixa o comportamento novo**;
- tem nome e docstring que dizem o que protege (ex.: `test_corte_de_cena_nao_emudece_cenas_seguintes`);
- **não chama serviços externos** (Gemini, Groq, OpenRouter, Tavily, GitHub, YouTube): use
  `monkeypatch`, funções falsas e arquivos gerados no próprio teste (`tmp_path`, `ffmpeg -f lavfi`);
- roda rápido (segundos) e não depende de chaves de API, do Chromium ou do Whisper, salvo se o
  teste for marcado com `@pytest.mark.lento`.

Antes de cada commit, rode a suíte e só faça commit com tudo passando:

```bash
.venv/Scripts/python.exe -m pytest -q
```

Se um teste antigo quebrar por mudança intencional de comportamento, atualize o teste no mesmo
commit e explique o porquê na mensagem do commit. Nunca apague nem pule (`skip`) um teste para
fazer a suíte passar.

## Outras regras do projeto

- Chaves de API nunca vão para o código, logs, commits ou chat: ficam nas variáveis de ambiente
  (PC: `setx`) e nos Secrets do GitHub.
- Commit, push, merge e disparo de execuções no GitHub só com pedido do usuário.
- `historico/temas.json` é atualizado pela própria rotina; não edite à mão.
- Arquivos em `saida/` são gerados e ficam fora do git.
- Python do projeto: `.venv` (Windows: `.venv/Scripts/python.exe`).
