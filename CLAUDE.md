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

## 6. MODELO DE DADOS

### 6.1 DDL (arquivo `sql/ddl/002_raw_tables.sql`)

```sql
CREATE SCHEMA IF NOT EXISTS `${PROJECT}.raw`;
CREATE SCHEMA IF NOT EXISTS `${PROJECT}.stg`;
CREATE SCHEMA IF NOT EXISTS `${PROJECT}.mart`;

-- Menções públicas de qualquer fonte (formato único)
CREATE TABLE IF NOT EXISTS `${PROJECT}.raw.mentions` (
  source       STRING    NOT NULL,   -- instagram_hashtag | youtube_video | youtube_comment | reddit | x | news
  mention_id   STRING    NOT NULL,   -- chave natural dentro da fonte
  published_at TIMESTAMP NOT NULL,
  date         DATE      NOT NULL,
  text         STRING,
  author_hash  STRING,               -- hash com sal; nunca o id real
  url          STRING,
  query_group  STRING,               -- marca | concorrente_a | concorrente_b ...
  language     STRING,
  engagement   INT64,                -- likes + comentários + compartilhamentos (quando houver)
  reach        INT64,
  metrics      STRING,               -- JSON em texto, métricas específicas da fonte
  _loaded_at   TIMESTAMP NOT NULL
)
PARTITION BY date
CLUSTER BY source, query_group;

-- Métricas diárias de contas próprias e séries agregadas
CREATE TABLE IF NOT EXISTS `${PROJECT}.raw.social_daily` (
  date        DATE   NOT NULL,
  platform    STRING NOT NULL,       -- instagram | youtube | gdelt
  metric      STRING NOT NULL,       -- reach | views | subscribers | news_tone:marca ...
  value       FLOAT64,
  _loaded_at  TIMESTAMP NOT NULL
)
PARTITION BY date;

-- Google Trends (interesse relativo 0-100)
CREATE TABLE IF NOT EXISTS `${PROJECT}.raw.trends_daily` (
  date        DATE   NOT NULL,
  term        STRING NOT NULL,
  geo         STRING NOT NULL,
  interest    INT64,
  _loaded_at  TIMESTAMP NOT NULL
)
PARTITION BY date;

-- Resultado do NLP (um registro por menção)
CREATE TABLE IF NOT EXISTS `${PROJECT}.raw.mention_labels` (
  source          STRING NOT NULL,
  mention_id      STRING NOT NULL,
  date            DATE   NOT NULL,
  sentiment       STRING,            -- positive | neutral | negative
  sentiment_score FLOAT64,
  topic           STRING,
  intent          STRING,            -- elogio | reclamacao | duvida | neutro
  model_version   STRING,
  classified_at   TIMESTAMP NOT NULL
)
PARTITION BY date;
```

### 6.2 Configuração de busca (`config/queries.yaml`)

```yaml
query_groups:            # termos de busca textual (YouTube, Reddit, X, GDELT)
  marca:
    - '"suamarca"'
    - '"sua marca"'
  concorrente_a:
    - '"concorrentea"'
  concorrente_b:
    - '"concorrenteb"'
hashtags:                # sem '#', sem espaço, sem emoji (limite de 30 por semana no Instagram)
  marca: [suamarca]
  concorrente_a: [concorrentea]
  concorrente_b: [concorrenteb]
trends_terms: [suamarca, concorrentea, concorrenteb]   # máx. 5 por chamada, com termo-âncora
geo: BR
```

### 6.3 Taxonomia de temas (`config/topics.yaml`)

```yaml
topics: [preco, qualidade, entrega, atendimento, produto_defeito, campanha_publicidade, institucional, concorrencia, outros]
```

---

## 7. FASES

### FASE 0: Fundação do repositório e do BigQuery

Tarefas:
- Criar a estrutura da seção 5, `README`, `.gitignore` (inclua `.env`, `data/`, `target/`), `.env.example`, `pyproject.toml` (ruff + pytest) e CI básico (`ruff` + `pytest`).
- Criar os DDLs da seção 6.1 e um script para aplicá-los.
- Implementar `src/common/*` (código abaixo).
- Implementar `src/cli.py`.

**`src/common/config.py`**

```python
import os
from pathlib import Path
import yaml


class Settings:
    gcp_project = os.environ.get("GCP_PROJECT", "")
    bq_location = os.environ.get("BQ_LOCATION", "US")
    salt = os.environ.get("AUTHOR_HASH_SALT", "")
    meta_graph_version = os.environ.get("META_GRAPH_VERSION", "v21.0")
    meta_token = os.environ.get("META_ACCESS_TOKEN", "")
    ig_user_id = os.environ.get("IG_USER_ID", "")
    youtube_key = os.environ.get("YOUTUBE_API_KEY", "")
    youtube_channel = os.environ.get("YOUTUBE_CHANNEL_ID", "")
    reddit_id = os.environ.get("REDDIT_CLIENT_ID", "")
    reddit_secret = os.environ.get("REDDIT_CLIENT_SECRET", "")
    x_token = os.environ.get("X_BEARER_TOKEN", "")
    slack_webhook = os.environ.get("SLACK_WEBHOOK_URL", "")
    sentiment_backend = os.environ.get("SENTIMENT_BACKEND", "hf")
    llm_model = os.environ.get("LLM_MODEL", "claude-haiku-5-5")


settings = Settings()


def _cfg(path: str = "config/queries.yaml") -> dict:
    return yaml.safe_load(Path(path).read_text(encoding="utf-8"))


def load_queries() -> dict[str, list[str]]:
    return _cfg()["query_groups"]


def load_hashtags() -> dict[str, list[str]]:
    return _cfg()["hashtags"]


def load_trends() -> tuple[list[str], str]:
    c = _cfg()
    return c["trends_terms"], c["geo"]
```

**`src/common/http.py`**

```python
import requests
from tenacity import retry, stop_after_attempt, wait_exponential


@retry(stop=stop_after_attempt(4), wait=wait_exponential(multiplier=2, max=60), reraise=True)
def get_json(url: str, **kwargs) -> dict:
    r = requests.get(url, timeout=30, **kwargs)
    r.raise_for_status()
    return r.json()
```

**`src/common/schema.py`**

```python
from __future__ import annotations
import hashlib
import json
from datetime import datetime, timezone


def hash_author(author_id: str | None, salt: str) -> str | None:
    if not author_id:
        return None
    return hashlib.sha256(f"{salt}:{author_id}".encode()).hexdigest()[:16]


def make_row(*, source: str, mention_id: str, published_at: datetime, text: str | None,
             url: str | None, query_group: str, author_id: str | None = None,
             language: str | None = None, engagement: int | None = None,
             reach: int | None = None, metrics: dict | None = None, salt: str = "") -> dict:
    if published_at.tzinfo is None:
        published_at = published_at.replace(tzinfo=timezone.utc)
    published_at = published_at.astimezone(timezone.utc)
    return {
        "source": source,
        "mention_id": str(mention_id),
        "published_at": published_at.isoformat(),
        "date": published_at.date().isoformat(),
        "text": (text or "").strip(),
        "author_hash": hash_author(author_id, salt),
        "url": url,
        "query_group": query_group,
        "language": language,
        "engagement": engagement,
        "reach": reach,
        "metrics": json.dumps(metrics or {}, ensure_ascii=False),
        "_loaded_at": datetime.now(timezone.utc).isoformat(),
    }
```

**`src/common/bq.py`** (upsert genérico e idempotente)

```python
from __future__ import annotations
import uuid
from google.cloud import bigquery
from .config import settings

F = bigquery.SchemaField
SCHEMAS = {
    "mentions": [F("source", "STRING", "REQUIRED"), F("mention_id", "STRING", "REQUIRED"),
                 F("published_at", "TIMESTAMP", "REQUIRED"), F("date", "DATE", "REQUIRED"),
                 F("text", "STRING"), F("author_hash", "STRING"), F("url", "STRING"),
                 F("query_group", "STRING"), F("language", "STRING"),
                 F("engagement", "INT64"), F("reach", "INT64"), F("metrics", "STRING"),
                 F("_loaded_at", "TIMESTAMP", "REQUIRED")],
    "social_daily": [F("date", "DATE", "REQUIRED"), F("platform", "STRING", "REQUIRED"),
                     F("metric", "STRING", "REQUIRED"), F("value", "FLOAT64"),
                     F("_loaded_at", "TIMESTAMP", "REQUIRED")],
    "trends_daily": [F("date", "DATE", "REQUIRED"), F("term", "STRING", "REQUIRED"),
                     F("geo", "STRING", "REQUIRED"), F("interest", "INT64"),
                     F("_loaded_at", "TIMESTAMP", "REQUIRED")],
    "mention_labels": [F("source", "STRING", "REQUIRED"), F("mention_id", "STRING", "REQUIRED"),
                       F("date", "DATE", "REQUIRED"), F("sentiment", "STRING"),
                       F("sentiment_score", "FLOAT64"), F("topic", "STRING"),
                       F("intent", "STRING"), F("model_version", "STRING"),
                       F("classified_at", "TIMESTAMP", "REQUIRED")],
}
KEYS = {
    "mentions": ["source", "mention_id", "date"],
    "social_daily": ["date", "platform", "metric"],
    "trends_daily": ["date", "term", "geo"],
    "mention_labels": ["source", "mention_id", "date"],
}


def upsert(table: str, rows: list[dict]) -> int:
    """Carrega em tabela temporária e faz MERGE. Reexecutar não duplica."""
    if not rows:
        return 0
    client = bigquery.Client(project=settings.gcp_project)
    staging = f"{settings.gcp_project}.raw._stg_{table}_{uuid.uuid4().hex[:8]}"
    client.load_table_from_json(
        rows, staging,
        job_config=bigquery.LoadJobConfig(schema=SCHEMAS[table], write_disposition="WRITE_TRUNCATE"),
    ).result()
    cols = [f.name for f in SCHEMAS[table]]
    on = " AND ".join(f"t.{k} = s.{k}" for k in KEYS[table])
    upd = ", ".join(f"t.{c} = s.{c}" for c in cols if c not in KEYS[table])
    sql = (f"MERGE `{settings.gcp_project}.raw.{table}` t USING `{staging}` s ON {on} "
           f"WHEN MATCHED THEN UPDATE SET {upd} WHEN NOT MATCHED THEN INSERT ROW")
    client.query(sql).result()
    client.delete_table(staging, not_found_ok=True)
    return len(rows)
```

**`src/cli.py`**

```python
import importlib
import json
from pathlib import Path
import typer
from src.common.bq import upsert

app = typer.Typer()
COLLECTORS = {
    "instagram_hashtag": "src.collectors.instagram_hashtag",
    "social_own": "src.collectors.social_own",
    "youtube": "src.collectors.youtube",
    "reddit": "src.collectors.reddit",
    "x_search": "src.collectors.x_search",
    "gdelt": "src.collectors.gdelt",
    "gdelt_tone": "src.collectors.gdelt_tone",
    "trends": "src.collectors.trends",
}


@app.command()
def collect(source: str, days: int = 2, dry_run: bool = False):
    """days=2 por padrão: reprocessa janela recente (plataformas revisam métricas)."""
    mod = importlib.import_module(COLLECTORS[source])
    rows = mod.collect(days=days)
    if dry_run:
        out = Path("data/dry_run"); out.mkdir(parents=True, exist_ok=True)
        (out / f"{source}.jsonl").write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows))
        typer.echo(f"[dry-run] {len(rows)} linhas em data/dry_run/{source}.jsonl")
    else:
        typer.echo(f"{upsert(mod.TABLE, rows)} linhas gravadas em raw.{mod.TABLE}")


@app.command()
def classify(limit: int = 2000):
    from src.nlp.classify import run
    typer.echo(f"{run(limit)} menções classificadas")


@app.command()
def alert():
    from src.alerts.slack_alert import run
    run()


if __name__ == "__main__":
    app()
```

**CHECKPOINT 0**: pare. Mostre a árvore, rode `ruff` e `pytest` verdes e confirme se os DDLs aplicam em um dataset de teste. Aguarde minha aprovação.

---

### FASE 1: Coletores de menções e de métricas próprias

Para cada coletor: implementar `TABLE`, `collect(days)`, teste com HTTP mockado e `--dry-run` validado. Padrão de cada linha: `make_row(...)`.

**`src/collectors/instagram_hashtag.py`**
Limites a respeitar (confirme na documentação): exige aprovação de App Review; **30 hashtags únicas por 7 dias**; `recent_media` só traz as últimas 24 horas; não expõe o username.

```python
from datetime import datetime
from dateutil import parser as dtp
from src.common.config import settings, load_hashtags
from src.common.http import get_json
from src.common.schema import make_row

TABLE = "mentions"
G = f"https://graph.facebook.com/{settings.meta_graph_version}"
MAX_HASHTAGS = 25  # folga sob o limite de 30 por semana


def collect(days: int = 1) -> list[dict]:
    rows, used = [], 0
    for group, tags in load_hashtags().items():
        for tag in tags:
            if used >= MAX_HASHTAGS:
                return rows
            h = get_json(f"{G}/ig_hashtag_search", params={
                "user_id": settings.ig_user_id, "q": tag, "access_token": settings.meta_token})
            used += 1
            hid = h["data"][0]["id"]
            media = get_json(f"{G}/{hid}/recent_media", params={
                "user_id": settings.ig_user_id, "access_token": settings.meta_token,
                "fields": "id,caption,like_count,comments_count,timestamp,permalink"}).get("data", [])
            for m in media:
                likes, comments = m.get("like_count") or 0, m.get("comments_count") or 0
                rows.append(make_row(
                    source="instagram_hashtag", mention_id=m["id"],
                    published_at=dtp.parse(m["timestamp"]), text=m.get("caption"),
                    url=m.get("permalink"), query_group=group, engagement=likes + comments,
                    metrics={"like_count": likes, "comments_count": comments, "hashtag": tag},
                    salt=settings.salt))
    return rows
```

**`src/collectors/social_own.py`** (contas próprias → `social_daily`)
As métricas e os parâmetros da Graph API mudam: **valide** `reach`, `views`, `follower_count` na documentação vigente antes de usar.

```python
from datetime import datetime, timedelta, timezone
from googleapiclient.discovery import build
from src.common.config import settings
from src.common.http import get_json

TABLE = "social_daily"
G = f"https://graph.facebook.com/{settings.meta_graph_version}"


def _now():
    return datetime.now(timezone.utc).isoformat()


def collect(days: int = 2) -> list[dict]:
    rows = []
    since = int((datetime.now(timezone.utc) - timedelta(days=days)).timestamp())
    until = int(datetime.now(timezone.utc).timestamp())
    # Instagram: insights diários da conta própria
    data = get_json(f"{G}/{settings.ig_user_id}/insights", params={
        "metric": "reach,views", "period": "day", "since": since, "until": until,
        "access_token": settings.meta_token}).get("data", [])
    for m in data:
        for v in m["values"]:
            rows.append({"date": v["end_time"][:10], "platform": "instagram",
                         "metric": m["name"], "value": float(v["value"]), "_loaded_at": _now()})
    # YouTube: snapshot diário do canal (inscritos e views totais); a diferença entre dias dá o ganho
    yt = build("youtube", "v3", developerKey=settings.youtube_key, cache_discovery=False)
    st = yt.channels().list(part="statistics", id=settings.youtube_channel).execute()["items"][0]["statistics"]
    today = datetime.now(timezone.utc).date().isoformat()
    for metric in ("subscriberCount", "viewCount", "videoCount"):
        rows.append({"date": today, "platform": "youtube", "metric": metric,
                     "value": float(st.get(metric, 0)), "_loaded_at": _now()})
    return rows
```

**`src/collectors/youtube.py`** (menções públicas; custo de cota é crítico)
Cota padrão: 10.000 unidades/dia; `search.list` custa 100; `commentThreads.list` custa 1. Mantenha um orçamento de segurança.

```python
from datetime import datetime, timedelta, timezone
from dateutil import parser as dtp
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from src.common.config import settings, load_queries
from src.common.schema import make_row

TABLE = "mentions"
UNIT_BUDGET = 8000  # nunca estoure a cota diária


def collect(days: int = 1) -> list[dict]:
    yt = build("youtube", "v3", developerKey=settings.youtube_key, cache_discovery=False)
    after = (datetime.now(timezone.utc) - timedelta(days=max(days, 1))).isoformat()
    units, rows = 0, []
    for group, terms in load_queries().items():
        for term in terms:
            if units + 100 > UNIT_BUDGET:
                return rows
            res = yt.search().list(q=term, part="snippet", type="video", order="date",
                                   publishedAfter=after, maxResults=25,
                                   relevanceLanguage="pt").execute()
            units += 100
            for it in res.get("items", []):
                vid, sn = it["id"]["videoId"], it["snippet"]
                rows.append(make_row(
                    source="youtube_video", mention_id=vid, published_at=dtp.parse(sn["publishedAt"]),
                    text=f'{sn["title"]}. {sn.get("description", "")}',
                    url=f"https://www.youtube.com/watch?v={vid}", query_group=group,
                    author_id=sn["channelId"], salt=settings.salt))
                try:
                    cts = yt.commentThreads().list(part="snippet", videoId=vid, maxResults=100,
                                                   textFormat="plainText", order="time").execute()
                    units += 1
                except HttpError:      # comentários desativados
                    continue
                for c in cts.get("items", []):
                    s = c["snippet"]["topLevelComment"]["snippet"]
                    likes = s.get("likeCount", 0)
                    rows.append(make_row(
                        source="youtube_comment", mention_id=c["id"],
                        published_at=dtp.parse(s["publishedAt"]), text=s["textDisplay"],
                        url=f"https://www.youtube.com/watch?v={vid}&lc={c['id']}",
                        query_group=group, author_id=s.get("authorChannelId", {}).get("value"),
                        engagement=likes, metrics={"like_count": likes, "video_id": vid},
                        salt=settings.salt))
    return rows
```

**`src/collectors/reddit.py`**
Atenção: a API oficial é gratuita só para uso **não comercial** aprovado (cerca de 100 consultas/min). Uso comercial exige acordo com o Reddit. Registre isso em `docs/LIMITATIONS.md` e deixe o coletor desativável por flag.

```python
from datetime import datetime, timezone
import praw
from src.common.config import settings, load_queries
from src.common.schema import make_row

TABLE = "mentions"


def collect(days: int = 1) -> list[dict]:
    r = praw.Reddit(client_id=settings.reddit_id, client_secret=settings.reddit_secret,
                    user_agent="brand-research/0.1")
    tf = "day" if days <= 1 else "week"
    rows = []
    for group, terms in load_queries().items():
        for term in terms:
            for s in r.subreddit("all").search(term, sort="new", time_filter=tf, limit=100):
                rows.append(make_row(
                    source="reddit", mention_id=s.id,
                    published_at=datetime.fromtimestamp(s.created_utc, tz=timezone.utc),
                    text=f"{s.title} {s.selftext}", url=f"https://reddit.com{s.permalink}",
                    query_group=group, author_id=str(s.author) if s.author else None,
                    engagement=s.score + s.num_comments,
                    metrics={"score": s.score, "num_comments": s.num_comments,
                             "subreddit": str(s.subreddit)}, salt=settings.salt))
    return rows
```

**`src/collectors/x_search.py`**
Modelo vigente: pago por uso (cerca de US$ 5 por mil posts lidos), busca recente de 7 dias. Implemente **teto de posts por execução** (`MAX_POSTS`) e registre o custo estimado no log.

```python
from datetime import datetime, timedelta, timezone
from dateutil import parser as dtp
from src.common.config import settings, load_queries
from src.common.http import get_json
from src.common.schema import make_row

TABLE = "mentions"
MAX_POSTS = 300  # teto de custo por execução


def collect(days: int = 1) -> list[dict]:
    start = (datetime.now(timezone.utc) - timedelta(days=min(days, 7))).isoformat()
    rows, total = [], 0
    for group, terms in load_queries().items():
        for term in terms:
            q = f"{term} -is:retweet lang:pt"
            token = None
            while total < MAX_POSTS:
                params = {"query": q, "max_results": 100, "start_time": start,
                          "tweet.fields": "created_at,public_metrics,lang,author_id"}
                if token:
                    params["next_token"] = token
                d = get_json("https://api.x.com/2/tweets/search/recent",
                             headers={"Authorization": f"Bearer {settings.x_token}"}, params=params)
                for t in d.get("data", []):
                    pm = t["public_metrics"]
                    rows.append(make_row(
                        source="x", mention_id=t["id"], published_at=dtp.parse(t["created_at"]),
                        text=t["text"], url=f"https://x.com/i/web/status/{t['id']}",
                        query_group=group, author_id=t.get("author_id"), language=t.get("lang"),
                        engagement=pm["like_count"] + pm["reply_count"] + pm["retweet_count"] + pm["quote_count"],
                        reach=pm.get("impression_count"), metrics=pm, salt=settings.salt))
                    total += 1
                token = d.get("meta", {}).get("next_token")
                if not token:
                    break
    return rows
```

**`src/collectors/gdelt.py`** (notícias e blogs; gratuito; **1 requisição a cada 5 s**)
Confirme na documentação o histórico disponível via API (relatos variam de 3 meses a 2017).

```python
import hashlib
import time
from datetime import datetime, timedelta, timezone
from gdeltdoc import GdeltDoc, Filters
from src.common.config import settings, load_queries
from src.common.schema import make_row

TABLE = "mentions"


def collect(days: int = 2) -> list[dict]:
    gd = GdeltDoc()
    end = datetime.now(timezone.utc).date()
    start = end - timedelta(days=max(days, 1))
    rows = []
    for group, terms in load_queries().items():
        for term in terms:
            f = Filters(keyword=term, country="BR", start_date=start.isoformat(), end_date=end.isoformat())
            df = gd.article_search(f)
            time.sleep(5)  # limite do DOC API
            for _, a in df.iterrows():
                ts = datetime.strptime(a["seendate"], "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
                rows.append(make_row(
                    source="news", mention_id=hashlib.sha1(a["url"].encode()).hexdigest()[:16],
                    published_at=ts, text=a["title"], url=a["url"], query_group=group,
                    language=a.get("language"), metrics={"domain": a.get("domain")}, salt=settings.salt))
    return rows
```

**`src/collectors/gdelt_tone.py`** (série diária de tom das notícias → `social_daily`)

```python
import time
from datetime import datetime, timedelta, timezone
from gdeltdoc import GdeltDoc, Filters
from src.common.config import load_queries

TABLE = "social_daily"


def collect(days: int = 7) -> list[dict]:
    gd, rows = GdeltDoc(), []
    end = datetime.now(timezone.utc).date()
    start = end - timedelta(days=max(days, 1))
    for group, terms in load_queries().items():
        f = Filters(keyword=terms[0], country="BR", start_date=start.isoformat(), end_date=end.isoformat())
        df = gd.timeline_search("timelinetone", f)
        time.sleep(5)
        vcol = df.columns[-1]  # nome da coluna varia; valide
        for _, r in df.iterrows():
            rows.append({"date": str(r["datetime"])[:10], "platform": "gdelt",
                         "metric": f"news_tone:{group}", "value": float(r[vcol]),
                         "_loaded_at": datetime.now(timezone.utc).isoformat()})
    return rows
```

**`src/collectors/trends.py`** (Google Trends, via `pytrends`, **não oficial e frágil**: trate falhas sem derrubar o pipeline)

```python
from datetime import datetime, timezone
from pytrends.request import TrendReq
from src.common.config import load_trends

TABLE = "trends_daily"


def collect(days: int = 90) -> list[dict]:
    terms, geo = load_trends()
    py = TrendReq(hl="pt-BR", tz=180)
    py.build_payload(terms[:5], timeframe="today 3-m", geo=geo)  # máx. 5 termos por chamada
    df = py.interest_over_time()
    rows = []
    for ts, r in df.iterrows():
        for t in terms[:5]:
            rows.append({"date": ts.date().isoformat(), "term": t, "geo": geo,
                         "interest": int(r[t]), "_loaded_at": datetime.now(timezone.utc).isoformat()})
    return rows
```

**Fontes que NÃO terão coletor nesta fase** (documente em `docs/LIMITATIONS.md`):
- **TikTok**: não há caminho oficial comercial para dados públicos (Research API é só acadêmica; as APIs de negócio expõem apenas a conta própria). Alternativas: dados da conta própria, amostragem manual ou provedor terceiro, avaliando risco de termos.
- **Reclame Aqui**: não há API pública oficial para terceiros. Existem scrapers de terceiros; decidir com jurídico antes (termos e LGPD).
- **Google Reviews**: a Places API devolve no máximo 5 reviews e restringe armazenamento; a Business Profile API traz tudo, mas só de perfis que a empresa administra. Fica no backlog (Fase 7).

**CHECKPOINT 1**: pare. Mostre a saída de `--dry-run` de cada coletor (5 linhas de amostra), o custo estimado por execução (cota YouTube, posts do X), e os testes verdes. Aguarde aprovação.

---

### FASE 2: Transformação com dbt

`dbt/dbt_project.yml` (trecho):

```yaml
name: brand_health
profile: brand_health
vars:
  brand_regex: "(?i)(suamarca|sua marca|suamarka)"
  gsc_dataset: searchconsole       # export nativo do Search Console (Projeto 1)
  ga4_dataset: analytics_000000000 # export nativo do GA4 (Projeto 1)
models:
  brand_health:
    staging:      {+materialized: view,  +schema: stg}
    intermediate: {+materialized: view,  +schema: stg}
    marts:        {+materialized: table, +schema: mart}
```

`dbt/seeds/campaign_calendar.csv` (preencher com as campanhas reais):

```csv
campaign_id,name,channel,objective,start_date,end_date
c001,Lancamento X,midia_paga,awareness,2026-09-01,2026-09-21
```

`models/sources.yml`:

```yaml
version: 2
sources:
  - name: raw
    schema: raw
    loaded_at_field: _loaded_at
    freshness: {warn_after: {count: 36, period: hour}}
    tables: [{name: mentions}, {name: social_daily}, {name: trends_daily}, {name: mention_labels}]
  - name: searchconsole
    schema: "{{ var('gsc_dataset') }}"
    tables: [{name: searchdata_site_impression}]
```

**`staging/stg_mentions.sql`**

```sql
select
  source, mention_id, published_at, date, text, author_hash, url,
  query_group, language, engagement, reach
from {{ source('raw', 'mentions') }}
where text is not null and length(text) > 0
qualify row_number() over (partition by source, mention_id order by _loaded_at desc) = 1
```

**`staging/stg_gsc_brand.sql`** (buscas de marca vindas do Projeto 1)

```sql
select
  data_date as date,
  sum(clicks) as brand_clicks,
  sum(impressions) as brand_impressions
from {{ source('searchconsole', 'searchdata_site_impression') }}
where query is not null
  and regexp_contains(query, r'{{ var("brand_regex") }}')
group by 1
```

**`staging/stg_ga4_brand.sql`** (sessões diretas e novos usuários, do export do GA4; ajuste ao seu dataset)

> **Corrigido em relação à versão original do prompt.** O export do GA4 tem uma linha por **evento**, não por sessão, e
> a versão original errava em quatro pontos: (1) usava `traffic_source.medium`, que é o **first touch do usuário** e não o
> meio da sessão; (2) `or traffic_source.medium is null` contava como "direto" todo evento sem consentimento;
> (3) `events_*` também casa `events_intraday_*` (e `'intraday_...' >= '2026...'` é verdadeiro em texto), duplicando o dia
> corrente; (4) a janela com `current_date()` não é reproduzível. A lógica abaixo foi testada em dados de exemplo; ainda
> falta validá-la contra o export real (passo 10 de `docs/DBT_PASSO_A_PASSO.md`).

```sql
-- Sessão = (user_pseudo_id, ga_session_id). O meio da sessão vem de event_params, não de traffic_source.
-- Consentimento negado chega sem user_pseudo_id (hipótese: a documentação não detalha): fica fora das sessões.
with events as (
  select
    parse_date('%Y%m%d', event_date) as date,
    user_pseudo_id,
    event_name,
    (select value.int_value from unnest(event_params) where key = 'ga_session_id') as ga_session_id,
    (select value.string_value from unnest(event_params) where key = 'medium') as medium
  from `{{ target.project }}.{{ var('ga4_dataset') }}.events_*`
  where regexp_contains(_table_suffix, r'^\d{8}$')            -- só tabelas diárias, exclui events_intraday_*
    and _table_suffix >= '{{ var("ga4_start_date", "20200101") }}'  -- limita os dias lidos (custo) de forma reproduzível
),
sessions as (
  select
    date, user_pseudo_id, ga_session_id,
    max(medium) as session_medium,                            -- 'medium' vem em session_start / 1ª page_view
    logical_or(event_name = 'first_visit') as is_new_user
  from events
  where user_pseudo_id is not null and ga_session_id is not null
  group by 1, 2, 3
)
select
  date,
  count(*) as sessions,
  countif(session_medium = '(none)') as direct_sessions,
  countif(is_new_user) as new_users
from sessions
group by 1
```

**`intermediate/int_mentions_labeled.sql`**

```sql
select m.*, l.sentiment, l.sentiment_score, l.topic, l.intent
from {{ ref('stg_mentions') }} m
left join {{ source('raw', 'mention_labels') }} l
  using (source, mention_id, date)
```

**`marts/mart_daily_brand_health.sql`** (tabela central, uma linha por dia)

```sql
with m as (
  select date,
    countif(query_group = 'marca') as mentions_brand,
    count(*) as mentions_total,
    countif(query_group = 'marca' and sentiment = 'positive') as pos,
    countif(query_group = 'marca' and sentiment = 'negative') as neg,
    sum(if(query_group = 'marca', coalesce(engagement, 0), 0)) as engagement_brand
  from {{ ref('int_mentions_labeled') }}
  group by date
),
tr as (
  select date,
    max(if(term = '{{ var("brand_term", "suamarca") }}', interest, null)) as trends_brand
  from {{ source('raw', 'trends_daily') }}
  group by date
)
select
  m.date, m.mentions_brand, m.mentions_total,
  safe_divide(m.mentions_brand, m.mentions_total)       as share_of_voice,
  safe_divide(m.pos - m.neg, m.mentions_brand)          as net_sentiment,
  m.engagement_brand,
  g.brand_clicks, g.brand_impressions,
  ga.direct_sessions, ga.new_users,
  tr.trends_brand
from m
left join {{ ref('stg_gsc_brand') }} g  using (date)
left join {{ ref('stg_ga4_brand') }} ga using (date)
left join tr using (date)
```

**`marts/mart_sov_weekly.sql`**

```sql
select
  date_trunc(date, week(monday)) as week,
  query_group,
  count(*) as mentions,
  safe_divide(count(*), sum(count(*)) over (partition by date_trunc(date, week(monday)))) as share_of_voice
from {{ ref('int_mentions_labeled') }}
group by week, query_group
```

**`marts/mart_topics_sentiment.sql`**

```sql
select
  date_trunc(date, week(monday)) as week, topic,
  count(*) as mentions,
  safe_divide(countif(sentiment='positive') - countif(sentiment='negative'), count(*)) as net_sentiment,
  avg(coalesce(engagement, 0)) as avg_engagement
from {{ ref('int_mentions_labeled') }}
where query_group = 'marca' and topic is not null
group by week, topic
```

**`marts/mart_lag_correlation.sql`** (em quantos dias um pico de menções vira pico de busca de marca)

```sql
select
  lag_days,
  corr(a.mentions_brand, b.brand_clicks) as correlation,
  count(*) as n_days
from unnest(generate_array(0, 14)) as lag_days
cross join {{ ref('mart_daily_brand_health') }} a
join {{ ref('mart_daily_brand_health') }} b
  on b.date = date_add(a.date, interval lag_days day)
group by lag_days
order by lag_days
```

**`marts/mart_campaign_impact.sql`**

```sql
select
  c.campaign_id, c.name, c.channel, c.objective,
  avg(if(h.date between date_sub(c.start_date, interval 7 day) and date_sub(c.start_date, interval 1 day), h.mentions_brand, null)) as mentions_before,
  avg(if(h.date between c.start_date and date_add(c.end_date, interval 7 day), h.mentions_brand, null)) as mentions_during_after,
  avg(if(h.date between date_sub(c.start_date, interval 7 day) and date_sub(c.start_date, interval 1 day), h.brand_clicks, null)) as brand_clicks_before,
  avg(if(h.date between c.start_date and date_add(c.end_date, interval 7 day), h.brand_clicks, null)) as brand_clicks_during_after
from {{ ref('campaign_calendar') }} c
cross join {{ ref('mart_daily_brand_health') }} h
group by 1, 2, 3, 4
```

**`marts/mart_crisis_alerts.sql`**

```sql
with d as (
  select date, neg,
    avg(neg)    over w as mu,
    stddev(neg) over w as sd
  from (select date, countif(sentiment = 'negative' and query_group = 'marca') as neg
        from {{ ref('int_mentions_labeled') }} group by date)
  window w as (order by date rows between 28 preceding and 1 preceding)
)
select date, neg, mu, sd, safe_divide(neg - mu, sd) as z_score
from d
where safe_divide(neg - mu, sd) > 2
```

**`schema.yml`** (testes mínimos; use `dbt_utils`)

```yaml
version: 2
models:
  - name: stg_mentions
    tests:
      - dbt_utils.unique_combination_of_columns:
          combination_of_columns: [source, mention_id]
    columns:
      - name: date
        tests: [not_null]
  - name: int_mentions_labeled
    columns:
      - name: sentiment
        tests:
          - accepted_values:
              values: [positive, neutral, negative]
              config: {where: "sentiment is not null"}
  - name: mart_daily_brand_health
    columns:
      - name: date
        tests: [unique, not_null]
```

**CHECKPOINT 2**: pare. Rode `dbt build` com dados de amostra (ou seeds sintéticos), mostre testes verdes e 10 linhas de `mart_daily_brand_health`. Aguarde aprovação.

---

### FASE 3: Classificação (sentimento, tema, intenção)

Regras: processar só menções ainda sem label; truncar texto; lotes; registrar `model_version`; backend de sentimento configurável (`hf` local ou `llm`).

**`src/nlp/classify.py`**

```python
import json
from datetime import datetime, timezone
import yaml
from google.cloud import bigquery
from src.common.bq import upsert
from src.common.config import settings

TOPICS = yaml.safe_load(open("config/topics.yaml"))["topics"]
SQL = """
select m.source, m.mention_id, m.date, m.text
from `{p}.raw.mentions` m
left join `{p}.raw.mention_labels` l using (source, mention_id, date)
where l.mention_id is null and m.date >= date_sub(current_date(), interval 7 day)
  and length(m.text) > 0
limit {n}
"""
SYSTEM = (
    "Você classifica menções de marca em português. Responda SOMENTE um JSON: "
    'uma lista de objetos {"id": <id>, "sentiment": "positive|neutral|negative", '
    '"topic": "<um de TOPICS>", "intent": "elogio|reclamacao|duvida|neutro"}. '
    "TOPICS = " + json.dumps(TOPICS, ensure_ascii=False)
)


def _hf_sentiment(texts):
    from transformers import pipeline
    clf = pipeline("text-classification", model="cardiffnlp/twitter-xlm-roberta-base-sentiment")
    return [(r["label"].lower(), float(r["score"])) for r in (clf(t[:512])[0] for t in texts)]


def _llm_batch(batch):
    import anthropic
    client = anthropic.Anthropic()
    payload = [{"id": i, "text": r["text"][:600]} for i, r in enumerate(batch)]
    msg = client.messages.create(model=settings.llm_model, max_tokens=2000, system=SYSTEM,
                                 messages=[{"role": "user", "content": json.dumps(payload, ensure_ascii=False)}])
    txt = msg.content[0].text.strip().removeprefix("```json").removesuffix("```").strip()
    return {o["id"]: o for o in json.loads(txt)}


def run(limit: int = 2000) -> int:
    client = bigquery.Client(project=settings.gcp_project)
    rows = [dict(r) for r in client.query(SQL.format(p=settings.gcp_project, n=limit)).result()]
    out, now = [], datetime.now(timezone.utc).isoformat()
    for i in range(0, len(rows), 20):
        batch = rows[i:i + 20]
        llm = _llm_batch(batch)
        hf = _hf_sentiment([r["text"] for r in batch]) if settings.sentiment_backend == "hf" else None
        for j, r in enumerate(batch):
            o = llm.get(j, {})
            sent, score = hf[j] if hf else (o.get("sentiment"), None)
            topic = o.get("topic") if o.get("topic") in TOPICS else "outros"
            out.append({"source": r["source"], "mention_id": r["mention_id"], "date": str(r["date"]),
                        "sentiment": sent, "sentiment_score": score, "topic": topic,
                        "intent": o.get("intent"), "model_version": f"{settings.sentiment_backend}+{settings.llm_model}",
                        "classified_at": now})
    return upsert("mention_labels", out)
```

Observação: o modelo HF devolve rótulos como `negative/neutral/positive`; confirme o mapeamento de rótulos do modelo escolhido. Crie um **conjunto de validação** (100 menções rotuladas à mão) e reporte acurácia por sentimento; ironia e gíria em português são o ponto fraco.

**CHECKPOINT 3**: pare. Mostre a distribuição de sentimento/tema em uma amostra, a acurácia no conjunto de validação e o custo estimado de LLM por 1.000 menções. Aguarde aprovação.

---

### FASE 4: Orquestração e deploy

**`Dockerfile`**

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
ENTRYPOINT ["python", "-m", "src.cli"]
```

**`infra/cloud_run_jobs.sh`** (um job por fonte; segredos via Secret Manager)

```bash
#!/usr/bin/env bash
set -euo pipefail
PROJECT=$GCP_PROJECT; REGION=us-central1
IMG=$REGION-docker.pkg.dev/$PROJECT/brand/listening:latest

for SRC in youtube reddit x_search gdelt gdelt_tone instagram_hashtag social_own trends; do
  gcloud run jobs deploy "brand-collect-$SRC" --image "$IMG" --region "$REGION" \
    --args="collect,$SRC" --set-env-vars="GCP_PROJECT=$PROJECT" \
    --set-secrets="YOUTUBE_API_KEY=youtube-api-key:latest,X_BEARER_TOKEN=x-bearer:latest,META_ACCESS_TOKEN=meta-token:latest,REDDIT_CLIENT_SECRET=reddit-secret:latest,AUTHOR_HASH_SALT=author-salt:latest"
done
gcloud run jobs deploy brand-classify --image "$IMG" --region "$REGION" --args="classify"
gcloud run jobs deploy brand-alert    --image "$IMG" --region "$REGION" --args="alert"
```

**`infra/scheduler.sh`** (exemplo; repita por job)

```bash
gcloud scheduler jobs create http brand-collect-youtube-daily \
  --location "$REGION" --schedule "0 6 * * *" --time-zone "America/Sao_Paulo" \
  --uri "https://$REGION-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/$PROJECT/jobs/brand-collect-youtube:run" \
  --http-method POST --oauth-service-account-email "$SA_EMAIL"
```

Ordem diária sugerida: coletores (06:00) → `classify` (07:00) → `dbt build` (07:30) → `alert` (08:00).

**Alternativa sem Cloud Scheduler: `.github/workflows/collect.yml`**

```yaml
name: collect
on:
  schedule: [{cron: "0 9 * * *"}]   # 09:00 UTC
  workflow_dispatch:
jobs:
  collect:
    runs-on: ubuntu-latest
    strategy:
      matrix: {source: [youtube, gdelt, gdelt_tone, reddit, x_search]}
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: {python-version: "3.11"}
      - run: pip install -r requirements.txt
      - uses: google-github-actions/auth@v2
        with: {credentials_json: "${{ secrets.GCP_SA_KEY }}"}
      - run: python -m src.cli collect ${{ matrix.source }}
        env:
          GCP_PROJECT: ${{ secrets.GCP_PROJECT }}
          YOUTUBE_API_KEY: ${{ secrets.YOUTUBE_API_KEY }}
          X_BEARER_TOKEN: ${{ secrets.X_BEARER_TOKEN }}
          AUTHOR_HASH_SALT: ${{ secrets.AUTHOR_HASH_SALT }}
```

Engenharia obrigatória: cargas idempotentes (MERGE), reprocesso dos últimos dias a cada execução (plataformas revisam métricas retroativamente), testes dbt, freshness das fontes, segredos fora do código, logs com contagem de linhas por execução.

**CHECKPOINT 4**: pare. Mostre uma execução ponta a ponta em ambiente de teste (coleta → classificação → dbt) e o custo mensal estimado (cota, posts do X, LLM, BigQuery). Aguarde aprovação.

---

### FASE 5: Alerta de crise

**`src/alerts/slack_alert.py`**

```python
from datetime import date, timedelta
import requests
from google.cloud import bigquery
from src.common.config import settings


def run():
    client = bigquery.Client(project=settings.gcp_project)
    y = (date.today() - timedelta(days=1)).isoformat()
    rows = list(client.query(
        f"select * from `{settings.gcp_project}.mart.mart_crisis_alerts` where date = '{y}'").result())
    if not rows:
        return
    r = rows[0]
    msg = (f":rotating_light: Alerta de reputação em {r['date']}: {r['neg']} menções negativas "
           f"(média 28d: {r['mu']:.1f}; z = {r['z_score']:.1f}). Veja o painel de brand health.")
    requests.post(settings.slack_webhook, json={"text": msg}, timeout=15)
```

---

### FASE 6: Painel no Looker Studio (especificação; o Claude Code gera o roteiro, eu monto o painel)

Fontes: `mart_daily_brand_health`, `mart_sov_weekly`, `mart_topics_sentiment`, `mart_lag_correlation`, `mart_campaign_impact`, `mart_crisis_alerts`.

Páginas:
1. **Visão geral**: scorecards (menções, SOV, net sentiment, cliques de marca) com variação vs. período anterior.
2. **Percepção vs. demanda**: série temporal de menções × cliques de marca × Trends; tabela de correlação defasada.
3. **Share of voice**: barras empilhadas por semana (marca × concorrentes).
4. **Temas**: barras de net sentiment e engajamento por tema.
5. **Campanhas**: antes × depois por campanha.
6. **Alertas**: tabela de dias com z-score > 2.

Entregue também `docs/DECISIONS.md` com a tabela sinal → decisão da seção 3, e um exemplo fictício completo (sinal, gatilho, decisão, resultado após 30 dias) para o portfólio.

**CHECKPOINT 6**: pare, entregue o roteiro e aguarde.

---

### FASE 7: Backlog de integráveis extras (propor, estimar e priorizar por esforço × impacto; **não implementar sem aprovação**)

1. Classificação de temas por LLM com taxonomia versionada (já parcialmente na Fase 3).
2. Reputação: notas e reviews (Google Business Profile apenas para locais próprios, App Store, Reclame Aqui se houver caminho legítimo), como série diária de nota média.
3. Share of search: busca da marca vs. concorrentes como proxy de participação de mercado.
4. Mídia espontânea: menções em imprensa com alcance estimado.
5. Creators e influenciadores: tabela de autores por alcance, sentimento e contribuição ao SOV (usando só `author_hash`).
6. Brand tracking contínuo: mini-pesquisa (Typeform/Forms → Sheets → BigQuery) para validar o listening com dado declarado.
7. Atendimento (SAC/Zendesk): volume e motivos de contato como sinal de percepção.

---

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

## 10. PRIMEIRA AÇÃO

Leia este documento por inteiro. Resuma em até 10 linhas o que entendeu, liste as **dúvidas e premissas que precisa que eu confirme** (nome da marca e concorrentes, projeto GCP, dataset do GA4/GSC, credenciais disponíveis, fontes que quero habilitar primeiro) e **aguarde minha resposta antes de executar a Fase 0**.
