# Social Listening & Brand Health (Projeto 2)

Pipeline de social listening: coleta menções públicas, classifica sentimento, tema e intenção, e gera marts de brand health no BigQuery.

Fluxo: `coleta (Python) → raw → dbt (stg → int → mart) → painel`. Um dataset por camada: `raw` (Python grava), `stg`, `int` e `mart` (dbt grava).

Comandos assumem Git Bash na raiz do repositório.

## Passo 1. Preparar o ambiente

```bash
python -m venv .venv && source .venv/Scripts/activate
pip install -r requirements-dev.txt
cp .env.example .env
```

Edite `.env`: preencha `GCP_PROJECT` e `AUTHOR_HASH_SALT` (`openssl rand -hex 32`). Deixe `BQ_DATASET_PREFIX` vazio (para o sandbox use `sandbox_`: datasets `sandbox_raw`, `sandbox_stg`...). Para coletar o YouTube, preencha também `YOUTUBE_API_KEY`.

**Verificar:** `ruff check . && pytest -q` sem erros.

## Passo 2. Autenticar no Google Cloud

```bash
gcloud auth application-default login
```

## Passo 3. Criar as tabelas raw no BigQuery

```bash
python -m scripts.apply_ddl --dry-run   # mostra o SQL
python -m scripts.apply_ddl             # aplica
```

**Verificar:** existem os datasets `raw`, `stg`, `int` e `mart`; `raw` tem as tabelas `mentions`, `social_daily`, `trends_daily` e `mention_labels`.

## Passo 4. Coletar dados

Fontes disponíveis: `youtube`, `google_news`, `trends`. Primeiro em `--dry-run` (grava `data/dry_run/<fonte>.jsonl`, sem tocar no BigQuery):

```bash
python -m src.cli collect youtube --dry-run
python -m src.cli collect google_news --dry-run
python -m src.cli collect trends --dry-run
```

Depois, sem `--dry-run`, para gravar no BigQuery. Reexecutar não duplica dados (MERGE por chave natural).

```bash
python -m src.cli collect youtube --days 7
```

Orçamento de cota do YouTube: 8.000 unidades por dia (uma execução de 7 dias gasta cerca de 610).

## Passo 5. Gerar dados sintéticos (GA4 e GSC)

Enquanto não há export real do Projeto 1:

```bash
python -m scripts.synthetic_data
```

Saída em `data/synthetic/<cenário>/`. Detalhes em `docs/DADOS_SINTETICOS.md`.

## Passo 6. Transformar com dbt

Siga `docs/DBT_PASSO_A_PASSO.md`: configurar `profiles.yml`, carregar os dados no sandbox, construir staging, intermediate e marts.

## Passo 7. Classificar e alertar (a partir das Fases 3 e 5)

```bash
python -m src.cli classify
python -m src.cli alert
```

## Referência

| Documento | Conteúdo |
|---|---|
| `docs/DBT_PASSO_A_PASSO.md` | construção dos modelos dbt |
| `docs/DADOS_SINTETICOS.md` | dados sintéticos |
| `docs/DECISIONS.md` | decisões de stack |
| `docs/LIMITATIONS.md` | limites das fontes |
| `CLAUDE.md` | plano completo por fases |
