# Decisões

## Stack de transformação
dbt-core + dbt-bigquery, comparado com Dagster, Dataform e SQL puro.
- Cumpre os critérios de aceite (unicidade, não nulo, valores aceitos, freshness, lineage) sem construir nada à mão.
- Dagster exigiria servidor ou daemon sempre ligado, fora do teto de custo (US$ 0 a 10 por mês).
- Dataform é boa alternativa nativa do GCP, mas com menos valor de portfólio.
- SQL puro não entrega testes nem lineage.

Orquestração: GitHub Actions cron (revisitar na Fase 4).

## Dataset único
Tudo em `social_listening_data_platform`. Camadas por prefixo de tabela: raw (nomes originais), `stg_*`, `int_*`, `mart_*`.
O macro `generate_schema_name` força o dataset do target. Perde-se permissão por camada.

## Dados
Marca proxy real (setor delivery/apps); GSC/GA4 sintéticos (flag `is_synthetic`). Ver `docs/LIMITATIONS.md`.
