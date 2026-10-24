# Social Listening & Brand Health (Projeto 2)

Pipeline interno de social listening: coleta menções públicas, classifica sentimento/tema/intenção e entrega marts de brand health no BigQuery.

O prompt original com o plano completo está em `CLAUDE.md`. Decisões do projeto: `docs/DECISIONS.md` e `.claude/specs/`.

## Setup rápido
```bash
python -m venv .venv && source .venv/Scripts/activate   # Windows (Git Bash)
pip install -r requirements-dev.txt
cp .env.example .env                                    # preencha GCP_PROJECT e AUTHOR_HASH_SALT
gcloud auth application-default login
python -m scripts.apply_ddl --dry-run                   # veja o SQL
python -m scripts.apply_ddl                             # aplica no BigQuery
ruff check . && pytest -q
```

## Uso
```bash
python -m src.cli collect youtube --dry-run   # grava data/dry_run/youtube.jsonl (a partir da Fase 1)
```

Dataset único `social_listening_data_platform`: raw (nomes originais), `stg_*`, `int_*`, `mart_*`.
