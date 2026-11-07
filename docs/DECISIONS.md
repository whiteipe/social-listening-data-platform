# Decisões

## Stack de transformação
dbt-core + dbt-bigquery, comparado com Dagster, Dataform e SQL puro.
- Cumpre os critérios de aceite (unicidade, não nulo, valores aceitos, freshness, lineage) sem construir nada à mão.
- Dagster exigiria servidor ou daemon sempre ligado, fora do teto de custo (US$ 0 a 10 por mês).
- Dataform é boa alternativa nativa do GCP, mas com menos valor de portfólio.
- SQL puro não entrega testes nem lineage.

Orquestração: GitHub Actions cron (revisitar na Fase 4).

## Um dataset por camada
`raw` (Python grava), `stg`, `int` e `mart` (dbt grava). Permite permissão e retenção por camada.
`BQ_DATASET_PREFIX` isola o sandbox (`sandbox_raw`, `sandbox_stg`...). O macro `generate_schema_name` usa o `+schema` da camada no target `prod` e `<dataset do target>_<camada>` nos demais.

## Dados
Marca proxy real (setor delivery/apps); GSC/GA4 sintéticos (flag `is_synthetic`). Ver `docs/LIMITATIONS.md`.
