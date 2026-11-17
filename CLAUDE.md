# PROMPT PARA CLAUDE CODE: Projeto 2, Social Listening & Brand Health (versão interna)

> Como usar: abra o Claude Code em um repositório vazio, cole este arquivo inteiro como primeira mensagem (ou salve como `CLAUDE.md` na raiz) e escreva: "Execute a Fase 0". Depois de cada checkpoint, revise e escreva "Aprovado, execute a Fase N".

---

## 1. PAPEL E OBJETIVO

Você é um engenheiro de dados sênior. Vai construir, em fases com checkpoints, um pipeline de **social listening interno** (sem Brandwatch, Talkwalker ou similares) que mede **impacto e saúde de marca** e entrega decisões de negócio para a diretoria.

Objetivo final:
1. Coletar menções e métricas orgânicas de fontes oficiais e abertas, via Python.
2. Armazenar tudo no BigQuery em camadas (`raw → stg → int → mart`), de forma idempotente.
3. Classificar sentimento, tema e intenção de cada menção.
4. Cruzar menções com buscas de marca (Search Console) e tráfego (GA4), vindos do Projeto 1.
5. Entregar um painel no Looker Studio e um alerta de crise.

Este projeto é o **Projeto 2 de uma escada de 3 projetos de Martech**:
- Projeto 1 (fundação): GA4 + GTM + Search Console, exportados para o BigQuery. **Premissa: já existe**, e este projeto só o consome.
- Projeto 2 (este): listening, redes orgânicas, Google Trends, brand health.
- Projeto 3 (futuro): MMM, brand lift e incrementalidade. Deixe o modelo de dados preparado (granularidade diária, chave por data, canal e região), mas **não o implemente**.

---

## 2. REGRAS DE EXECUÇÃO (OBRIGATÓRIAS)

1. Trabalhe **por fases**. Ao fim de cada fase, **pare** e entregue: (a) resumo do que foi feito, (b) árvore de arquivos criados, (c) comandos para eu verificar, (d) riscos e dúvidas. **Não inicie a fase seguinte sem eu aprovar.**
2. Antes de usar qualquer API, **confirme na documentação vigente** os nomes de endpoints, campos, métricas, versões, preços e limites. Eles mudam (a API do X passou a ser paga por uso em 2026, os termos do Reddit foram revisados em 2026). Se a documentação divergir deste prompt, siga a documentação e me avise.
3. **Nunca** coloque segredos no código ou no git. Use variáveis de ambiente (`.env` local, Secret Manager em produção) e mantenha `.env.example` atualizado.
4. Todo coletor deve ter: `--dry-run` (grava JSONL local, sem tocar no BigQuery), retry com backoff, guarda de cota/custo, logs estruturados e teste unitário com HTTP mockado.
5. Todo carregamento é **idempotente** (MERGE por chave natural). Reexecutar não duplica dados.
6. Tudo em **UTC**; datas em `DATE`; nomes em `snake_case`.
7. **LGPD**: nunca armazene identificadores de autor em claro. Use hash com sal (`author_hash`). Guarde o mínimo necessário.
8. **Termos de uso**: respeite os termos de cada plataforma. Não faça scraping de fontes que o proíbem. Onde não houver caminho oficial, registre no `docs/LIMITATIONS.md` em vez de contornar.
9. Se algo estiver ambíguo, **pergunte** antes de assumir.

---

## 3. CONTEXTO DE NEGÓCIO (por que isso existe)

O painel não decide sozinho. Ele transforma sinais em perguntas e perguntas em ações para a diretoria:

| Área | Sinal (gatilho) | Decisão |
|---|---|---|
| Mídia | Share of voice e buscas de marca em queda por 3 a 4 semanas vs. concorrentes | Reforçar mídia de topo de funil (validar no Projeto 3) |
| Mídia | Menções sobem, mas busca de marca não | Revisar canal/criativo; mais verba não resolve |
| Conteúdo | Tema com alcance e sentimento acima da média móvel | Replicar formato e pauta no calendário editorial |
| Produto/atendimento | Mesmo tema negativo recorrente por vários dias; alerta de crise | Acionar produto e SAC, priorizar no roadmap |
| Posicionamento | Temas associados à marca diferem do posicionamento pretendido | Ajustar narrativa, mensagem e porta-vozes |

Ressalva obrigatória a registrar na documentação: o Projeto 2 mostra **correlação**; causalidade se comprova no Projeto 3 (incrementalidade e MMM).

### Métricas (definições canônicas)

- **Share of voice (SOV)** = menções da marca ÷ (menções da marca + concorrentes).
- **Net sentiment** = (positivas − negativas) ÷ menções da marca.
- **Engajamento orgânico** por post e por plataforma; **alcance** quando disponível.
- **Correlação defasada**: correlação entre menções da marca e cliques de marca (GSC) com defasagem de 0 a 14 dias.
- **Impacto de campanha**: média de menções nos 7 dias antes vs. 7 dias depois de cada campanha (`campaign_calendar`).
- **Alerta de crise**: menções negativas do dia acima de 2 desvios-padrão da média móvel de 28 dias.

---

## 4. STACK E PREMISSAS

- Cloud: GCP (BigQuery, Cloud Run Jobs, Cloud Scheduler, Secret Manager). Alternativa de orquestração: GitHub Actions com cron.
- Linguagem: Python 3.11. Transformação: dbt-bigquery. BI: Looker Studio.
- Dependências Python: `requests`, `tenacity`, `typer`, `pyyaml`, `python-dateutil`, `pandas`, `google-cloud-bigquery`, `google-api-python-client`, `praw`, `gdeltdoc`, `pytrends`, `anthropic`, e (opcionais, na imagem de NLP) `transformers`, `torch`. Dev: `pytest`, `responses`, `ruff`.
- Variáveis de ambiente (documente todas em `.env.example`):

```bash
GCP_PROJECT=
BQ_LOCATION=US
AUTHOR_HASH_SALT=            # gere aleatório e guarde no Secret Manager
META_GRAPH_VERSION=v21.0     # confirmar versão vigente
META_ACCESS_TOKEN=
IG_USER_ID=
YOUTUBE_API_KEY=
YOUTUBE_CHANNEL_ID=
REDDIT_CLIENT_ID=
REDDIT_CLIENT_SECRET=
X_BEARER_TOKEN=
SLACK_WEBHOOK_URL=
SENTIMENT_BACKEND=hf         # hf | llm
LLM_MODEL=claude-haiku-5-5   # confirmar na documentação vigente
ANTHROPIC_API_KEY=
BRAND_REGEX=(?i)(suamarca|sua marca|suamarka)   # inclua erros de grafia
```

---

## 5. HIERARQUIA DO REPOSITÓRIO

```
brand-health-listening/
├── CLAUDE.md                      # este prompt (opcional)
├── README.md
├── .env.example
├── .gitignore
├── Dockerfile
├── requirements.txt               # coleta
├── requirements-nlp.txt           # transformers + torch (imagem de classificação)
├── pyproject.toml                 # ruff + pytest
├── config/
│   ├── queries.yaml               # grupos de busca: marca, concorrentes, hashtags
│   └── topics.yaml                # taxonomia de temas
├── sql/
│   └── ddl/
│       ├── 001_datasets.sql
│       └── 002_raw_tables.sql
├── src/
│   ├── cli.py                     # typer: collect | classify | alert
│   ├── common/
│   │   ├── config.py
│   │   ├── http.py
│   │   ├── schema.py
│   │   └── bq.py
│   ├── collectors/
│   │   ├── instagram_hashtag.py   # mentions
│   │   ├── social_own.py          # social_daily (Instagram e YouTube próprios)
│   │   ├── youtube.py             # mentions
│   │   ├── reddit.py              # mentions
│   │   ├── x_search.py            # mentions
│   │   ├── gdelt.py               # mentions (notícias)
│   │   ├── gdelt_tone.py          # social_daily (tom das notícias)
│   │   └── trends.py              # trends_daily
│   ├── nlp/
│   │   └── classify.py            # sentimento + tema + intenção
│   └── alerts/
│       └── slack_alert.py
├── dbt/
│   ├── dbt_project.yml
│   ├── profiles.yml.example
│   ├── seeds/
│   │   └── campaign_calendar.csv
│   └── models/
│       ├── sources.yml
│       ├── schema.yml             # testes
│       ├── staging/
│       │   ├── stg_mentions.sql
│       │   ├── stg_gsc_brand.sql
│       │   └── stg_ga4_brand.sql
│       ├── intermediate/
│       │   └── int_mentions_labeled.sql
│       └── marts/
│           ├── mart_daily_brand_health.sql
│           ├── mart_sov_weekly.sql
│           ├── mart_topics_sentiment.sql
│           ├── mart_lag_correlation.sql
│           ├── mart_campaign_impact.sql
│           └── mart_crisis_alerts.sql
├── tests/
│   ├── test_schema.py
│   └── collectors/test_*.py
├── infra/
│   ├── cloud_run_jobs.sh
│   └── scheduler.sh
├── .github/workflows/
│   ├── ci.yml
│   └── collect.yml                # alternativa ao Cloud Scheduler
└── docs/
    ├── ARCHITECTURE.md
    ├── DATA_DICTIONARY.md
    ├── DECISIONS.md               # tabela sinal → decisão (seção 3)
    └── LIMITATIONS.md
```

### Hierarquia das camadas de dados

```
raw (bruto, imutável, particionado por date)
 └─ stg (tipos corrigidos, deduplicado, nomes padronizados)
     └─ int (enriquecido: junção com labels de NLP)
         └─ mart (pronto para dashboard e alertas)
dim/seed: campaign_calendar, taxonomia de temas, grupos de busca
```

---

## 6–7, 10. MODELO DE DADOS, FASES E PRIMEIRA AÇÃO

Em `docs/SPEC.md` (DDL, `queries.yaml`, `topics.yaml`, fases 0–7 com critérios). Ler a seção da fase antes de trabalhar nela.

## 8. LIMITAÇÕES E COMPLIANCE (gerar `docs/LIMITATIONS.md` com isto)

- **Cobertura**: X é pago por post lido e limitado a 7 dias de busca; Reddit comercial exige acordo; TikTok e Instagram público são praticamente fechados (Instagram: 30 hashtags/semana, últimas 24 h, sem usuário). Ferramentas pagas costumam ter contratos de dados que este projeto não tem.
- **Histórico**: dados públicos não têm passado anterior ao início da coleta. Comece cedo.
- **Qualidade**: deduplicação, filtro de spam/bots e sentimento em português (ironia, gíria) exigem validação contínua.
- **Manutenção**: APIs, preços e termos mudam. Monitore avisos das plataformas.
- **Legal**: respeitar termos de uso e LGPD (hash de autor, retenção mínima, sem dados sensíveis). Reviews do Google têm restrições de armazenamento. Scraping só com respaldo jurídico.
- **Causalidade**: o projeto mostra correlação; comprove impacto no Projeto 3.

---

## 9. CRITÉRIOS DE ACEITE

- [ ] `ruff` e `pytest` verdes; cobertura de teste para `schema.py`, `bq.py` e cada coletor (HTTP mockado).
- [ ] Reexecutar qualquer coletor não duplica dados (teste de idempotência).
- [ ] Nenhum segredo ou identificador de autor em claro no repositório ou no BigQuery.
- [ ] `dbt build` passa com testes de unicidade, não nulo, valores aceitos e freshness.
- [ ] `mart_daily_brand_health` tem uma linha por dia e todas as métricas da seção 3.
- [ ] Orçamento de cota/custo documentado e respeitado (YouTube ≤ 8.000 unidades/dia; X ≤ `MAX_POSTS` por execução).
- [ ] Documentação: `ARCHITECTURE.md`, `DATA_DICTIONARY.md`, `DECISIONS.md`, `LIMITATIONS.md`.
- [ ] Acurácia do sentimento medida em conjunto de validação e reportada.

---
