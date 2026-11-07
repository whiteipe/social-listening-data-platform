# dbt passo a passo: do zero até os marts

Guia para aprender dbt construindo este projeto. Cada passo tem **Por quê**, **Fazer** e **Verificar**.
Fazemos juntos: eu mostro o comando e o motivo, você roda ou me pede para rodar, e perguntamos o que surgir.
Marque os passos concluídos em `[ ]`.

**Como usar:** você digita cada arquivo e cada comando. Se algo falhar, pare, cole a mensagem de erro e resolvemos
juntos: não pule para o passo seguinte. O código deste guia ainda não foi executado de ponta a ponta; um erro é esperado
e faz parte do aprendizado.

**Convenções:**
- Terminal: Git Bash, na raiz do repositório, com o ambiente ativado: `source .venv/Scripts/activate`.
- Comandos `dbt` rodam dentro da pasta `dbt/`: `cd dbt`.
- Ao criar um arquivo, o caminho vem no texto do passo, relativo à raiz do repositório.

---

## Parte A. Fundamentos

### [ ] 1. O que o dbt faz (e o que não faz)

**Por quê:** dbt cuida só do **T** de ELT. Ele não coleta nem carrega dados: pega tabelas que já estão no BigQuery
e as transforma com `SELECT`, na ordem certa, com testes.

| Conceito dbt | Para que serve | No nosso projeto |
|---|---|---|
| **source** | declara uma tabela que o dbt não cria | as tabelas `raw` (menções, GA4, GSC) |
| **model** | um arquivo `.sql` com um `SELECT` | `stg_*`, `int_*`, `mart_*` |
| **ref()** | liga um modelo a outro; dbt deduz a ordem (o DAG) | `{{ ref('stg_mentions') }}` |
| **materialization** | como o `SELECT` vira objeto: `view`, `table`, `incremental` | staging e intermediate = view, marts = table |
| **test** | afirmação sobre os dados (`unique`, `not_null`...) | chaves únicas, valores aceitos |
| **seed** | CSV pequeno versionado, carregado como tabela | `campaign_calendar` |
| **macro** | função Jinja reutilizável | `generate_schema_name` |

Os datasets do projeto: `raw` (o Python grava), `stg`, `int` e `mart` (o dbt grava). No sandbox, os mesmos nomes com
prefixo `sandbox_`.

**Verificar:** você consegue explicar por que a coleta (Python) e a transformação (dbt) ficam separadas.

### [ ] 2. Ambiente e conexão

**Por quê:** o dbt precisa saber *onde* rodar (projeto, dataset, localização). Isso fica em `profiles.yml`, **fora do
repositório**, porque descreve a máquina de quem roda (e pode ter credenciais).

**Fazer:**
1. Confira a versão (fixada em `requirements.txt`): `dbt --version` deve mostrar `dbt-core 1.12.6` e `bigquery 1.12.1`.
2. Crie a pasta e o arquivo de conexão (no Windows ele fica em `C:\Users\<você>\.dbt\profiles.yml`):
   ```bash
   mkdir -p ~/.dbt
   cp dbt/profiles.yml.example ~/.dbt/profiles.yml
   ```
3. Abra `~/.dbt/profiles.yml` e deixe assim (troque `SEU_PROJETO_GCP` pelo valor de `GCP_PROJECT` do seu `.env`):
   ```yaml
   brand_health:
     target: dev
     outputs:
       dev:
         type: bigquery
         method: oauth             # usa o login do gcloud (passo 2 do README)
         project: SEU_PROJETO_GCP
         dataset: sandbox          # o dbt cria sandbox_stg, sandbox_int e sandbox_mart
         location: US
         threads: 4
         maximum_bytes_billed: 1000000000   # 1 GB: o BigQuery recusa consultas que leriam mais
   ```
   O `dataset: sandbox` mantém seus testes longe de `stg`, `int` e `mart`. `maximum_bytes_billed` é uma trava barata
   contra erro de custo.
4. Teste a conexão:
   ```bash
   cd dbt
   dbt debug
   ```

**Verificar:** `dbt debug` termina com `All checks passed!`.

### [ ] 3. Estrutura do projeto

**Por quê:** saber o que cada arquivo faz evita mexer no lugar errado.

```
dbt/
├── dbt_project.yml        # nome, caminhos, variáveis, materialization e dataset por pasta
├── packages.yml           # dependências (dbt_utils): vamos criar no passo 7
├── macros/                # generate_schema_name.sql: dataset por camada
├── seeds/                 # campaign_calendar.csv
└── models/
    ├── sources.yml        # declara o raw (passo 5)
    ├── schema.yml         # testes e documentação (passo 7)
    ├── staging/           # 1 modelo por fonte: limpa tipos, nomes, dedupe
    ├── intermediate/      # junta e enriquece
    └── marts/             # tabelas finais, uma por pergunta de negócio
```

Abra `dbt/dbt_project.yml` e `dbt/macros/generate_schema_name.sql` e leia. Em `dbt_project.yml`, a linha
`staging: {+materialized: view, +schema: stg}` diz: modelos desta pasta viram *views* no dataset `stg`.

**Por quê do macro:** por padrão o dbt nomeia o dataset `<dataset do target>_<camada>`. O macro `generate_schema_name`
faz o target `prod` usar só o nome da camada (`stg`, `int`, `mart`); os demais targets mantêm o prefixo
(`sandbox_stg`).

**Fazer:** `cd dbt && dbt parse`.

**Verificar:** `dbt parse` roda sem erro. Pode aparecer um aviso de "unused configuration paths": é esperado, as pastas
de modelos ainda estão vazias.

---

## Parte B. Dados e o primeiro modelo

### [ ] 4. Carregar os dados sintéticos no sandbox

**Por quê:** o dbt só transforma o que já existe. Precisamos do "L" (load) fora dele. É o mesmo papel que o Python faz
com os dados reais, mas aqui lemos os arquivos de `data/synthetic/`.

**Fazer:**
1. Gere os dados (se `data/synthetic/realistic/` ainda não existir), da raiz do repositório:
   ```bash
   python -m scripts.synthetic_data
   ```
2. Crie `scripts/load_synthetic.py`:
   ```python
   """Carrega os dados sintéticos locais no sandbox do BigQuery (nunca no raw de produção).

   Uso: python -m scripts.load_synthetic [--scenario realistic|lag3]
   Recarrega (WRITE_TRUNCATE) as tabelas em `sandbox_raw`: pode rodar de novo à vontade.
   """
   import argparse
   import gzip
   from pathlib import Path

   from google.cloud import bigquery

   from src.common.bq import SCHEMAS
   from src.common.config import settings

   RAW = "sandbox_raw"
   F = bigquery.SchemaField
   GSC_SCHEMA = [F("data_date", "DATE"), F("site_url", "STRING"), F("query", "STRING"),
                 F("is_anonymized_query", "BOOLEAN"), F("country", "STRING"), F("device", "STRING"),
                 F("impressions", "INT64"), F("clicks", "INT64"), F("data_state", "STRING"),
                 F("is_synthetic", "BOOLEAN"), F("_loaded_at", "TIMESTAMP")]


   def _load(client, table, path, schema, gz=False):
       opener = gzip.open if gz else open
       with opener(path, "rb") as f:
           job = client.load_table_from_file(
               f, f"{settings.gcp_project}.{RAW}.{table}",
               job_config=bigquery.LoadJobConfig(
                   schema=schema, source_format="NEWLINE_DELIMITED_JSON",
                   write_disposition="WRITE_TRUNCATE"))
       job.result()
       return job.output_rows


   def main(scenario):
       src = Path("data/synthetic") / scenario
       if not src.exists():
           raise SystemExit(f"{src} não existe. Rode antes: python -m scripts.synthetic_data")
       client = bigquery.Client(project=settings.gcp_project, location=settings.bq_location)
       client.create_dataset(bigquery.Dataset(f"{settings.gcp_project}.{RAW}"), exists_ok=True)
       for table, schema in SCHEMAS.items():
           print(table, _load(client, table, src / f"{table}.jsonl", schema))
       print("gsc", _load(client, "gsc", src / "gsc.jsonl", GSC_SCHEMA))
       ga4_schema = client.schema_from_json(src / "ga4" / "schema.json")
       shards = sorted((src / "ga4").glob("events_*.jsonl.gz"))
       for i, p in enumerate(shards, 1):
           _load(client, p.name.removesuffix(".jsonl.gz"), p, ga4_schema, gz=True)
           if i % 25 == 0 or i == len(shards):
               print(f"ga4: {i}/{len(shards)} tabelas")


   if __name__ == "__main__":
       ap = argparse.ArgumentParser()
       ap.add_argument("--scenario", choices=["realistic", "lag3"], default="realistic")
       main(ap.parse_args().scenario)
   ```
3. Rode da raiz do repositório (leva cerca de 12 minutos: são 149 tabelas do GA4, uma por dia, carregadas uma a uma):
   ```bash
   python -m scripts.load_synthetic
   ```

   O GA4 real também é fragmentado por dia (`events_20260528`, `events_20260529`...), e é por isso que o dbt o lê com
   curinga (`events_*`).

**Verificar:** `bq ls sandbox_raw` mostra `mentions`, `mention_labels`, `social_daily`, `trends_daily`, `gsc` e 149
tabelas `events_*`. Custo: centavos.

### [ ] 5. Declarar as fontes (`sources`) e a frescura

**Por quê:** `source()` registra de onde o dado vem. Assim o dbt entende a linhagem (o que alimenta o quê) e pode checar
se o dado está **atualizado** (`freshness`), em vez de você descobrir no painel.

**Fazer:** crie `dbt/models/sources.yml`:
```yaml
version: 2

sources:
  - name: raw
    # prod lê o dataset raw; os outros targets leem <dataset do target>_raw (ex.: sandbox_raw)
    schema: "{{ 'raw' if target.name == 'prod' else target.schema ~ '_raw' }}"
    loaded_at_field: _loaded_at
    freshness:
      warn_after: {count: 36, period: hour}
    tables:
      - name: mentions
      - name: social_daily
      - name: trends_daily
      - name: mention_labels

  - name: search_console
    schema: "{{ 'raw' if target.name == 'prod' else target.schema ~ '_raw' }}"
    tables:
      - name: gsc            # export do Search Console (sintético no sandbox)

  - name: ga4
    schema: "{{ 'raw' if target.name == 'prod' else target.schema ~ '_raw' }}"
    tables:
      - name: events         # uma tabela por dia: events_20260528, events_20260529...
        identifier: events_*
```

Entenda as peças: o `schema` usa Jinja (`{{ ... }}`) para escolher `sandbox_raw` no seu target `dev` e `raw` no `prod`.
O `identifier: events_*` faz o dbt ler todas as tabelas diárias de uma vez.

Depois:
```bash
cd dbt
dbt source freshness
```

**Verificar:** a checagem retorna `PASS` ou `WARN` por tabela. Em dado sintético o `WARN` é esperado: o `_loaded_at`
envelhece. Você sabe explicar por quê?

### [ ] 6. Primeiro modelo: `stg_mentions`

**Por quê:** é a "camada de limpeza": um modelo por tabela de origem, sem regra de negócio. Um `SELECT` simples já
mostra todo o ciclo do dbt.

**Fazer:**
1. Crie `dbt/models/staging/stg_mentions.sql`:
   ```sql
   -- Uma linha por menção (source + mention_id). Sem regra de negócio, só limpeza.
   select
       source,
       mention_id,
       published_at,
       date(published_at, 'America/Sao_Paulo') as date,   -- data de Brasília; o raw guarda a data em UTC
       text,
       author_hash,
       url,
       query_group,
       language,
       engagement,
       reach
   from {{ source('raw', 'mentions') }}
   where text is not null
     and length(text) > 0
   -- a mesma menção pode ser regravada com outra data UTC: fica a carga mais recente
   qualify row_number() over (
       partition by source, mention_id
       order by _loaded_at desc, published_at desc
   ) = 1
   ```
   O `qualify` é o dedupe: numera as cópias de cada menção, da mais recente para a mais antiga, e fica com a primeira.
2. Rode: `dbt run --select stg_mentions`
3. Abra `dbt/target/compiled/brand_health/models/staging/stg_mentions.sql`: é o SQL que o dbt realmente enviou (Jinja
   já resolvido). Compare com o seu.
4. Consulte a view no BigQuery:
   ```bash
   bq query --use_legacy_sql=false 'select count(*) from sandbox_stg.stg_mentions'
   ```

**Verificar:** a view existe em `sandbox_stg`. A contagem deve ser menor que as 4.562 linhas de `sandbox_raw.mentions`
(o dedupe e o filtro de texto removem linhas): descubra quantas e por quê.

### [ ] 7. Testes e o pacote `dbt_utils`

**Por quê:** teste é a razão de usar dbt. Em vez de achar um erro no painel, o `dbt test` falha antes.

**Fazer:**
1. Crie `dbt/packages.yml`:
   ```yaml
   packages:
     - package: dbt-labs/dbt_utils
       version: 1.3.0
   ```
   e rode `dbt deps` (instala o pacote em `dbt_packages/`).
2. Crie `dbt/models/schema.yml`:
   ```yaml
   version: 2

   models:
     - name: stg_mentions
       columns:
         - name: date
           tests: [not_null]
       tests:
         - dbt_utils.unique_combination_of_columns:
             combination_of_columns: [source, mention_id]
   ```
3. `dbt test --select stg_mentions`
4. **Quebre de propósito:** em `stg_mentions.sql`, comente as linhas do `qualify ... = 1`, rode
   `dbt run --select stg_mentions` e depois o teste. Ele deve falhar. Leia a saída e abra o SQL do teste em
   `target/compiled/`. Depois desfaça o comentário e rode os dois comandos de novo.

**Verificar:** testes verdes no final; você sabe ler o SQL do teste que falhou.

### [ ] 8. Seeds: `campaign_calendar`

**Por quê:** dados pequenos e estáticos (calendário de campanhas) cabem num CSV versionado: revisão por pull request e
nenhuma carga separada. Mas só para dado de referência, nunca para dado grande.

**Fazer:**
1. Copie as campanhas sintéticas (o arquivo atual só tem o cabeçalho), da raiz do repositório:
   ```bash
   cp data/synthetic/realistic/campaign_calendar.csv dbt/seeds/campaign_calendar.csv
   ```
2. Em `dbt/dbt_project.yml`, no fim do arquivo, adicione o bloco `seeds` (o dbt não adivinha bem o tipo de data):
   ```yaml
   seeds:
     brand_health:
       +schema: stg
       campaign_calendar:
         +column_types: {start_date: date, end_date: date}
   ```
3. `cd dbt && dbt seed`

**Verificar:** a tabela `sandbox_stg.campaign_calendar` tem 3 campanhas, com `is_synthetic = true`.

---

## Parte C. Camadas com as dificuldades reais

### [ ] 9. `stg_gsc_brand`: revisão, anônimos e ruído do regex

**Por quê:** o Search Console chega com atraso, os últimos dias são **preliminares** (valem ~70%) e parte dos cliques vem
sem texto de busca. Além disso, "vivo" aparece em buscas que não são da marca ("tv ao vivo"). Tratar errado distorce
justamente a série que vamos correlacionar.

**Fazer:**
1. Em `dbt/dbt_project.yml`, dentro de `vars:`, acrescente (o regex fica em duas partes porque o BigQuery não aceita
   lookbehind, então "exceto ao vivo" não cabe numa expressão só):
   ```yaml
     brand_exclude_regex: '(?i)\bao vivo\b'
   ```
2. Crie `dbt/models/staging/stg_gsc_brand.sql`:
   ```sql
   -- Cliques e impressões de buscas de marca no Google, por dia.
   -- Só dias finais: os preliminares valem cerca de 70% e distorceriam a série.
   select
       data_date as date,
       sum(clicks) as brand_clicks,
       sum(impressions) as brand_impressions
   from {{ source('search_console', 'gsc') }}
   where data_state = 'final'
     and not is_anonymized_query          -- cliques anônimos não têm texto para classificar
     and regexp_contains(query, r'{{ var("brand_regex") }}')
     and not regexp_contains(query, r'{{ var("brand_exclude_regex") }}')
   group by date
   ```
3. `dbt run --select stg_gsc_brand`
4. Adicione ao `schema.yml`, dentro de `models:`:
   ```yaml
     - name: stg_gsc_brand
       columns:
         - name: date
           tests: [unique, not_null]
   ```
   e rode `dbt test --select stg_gsc_brand`.

Limite conhecido: o Search Console usa o dia do fuso do Pacífico e o resto do projeto usa Brasília. Em dado diário não
dá para corrigir; aceitamos até 1 dia de deslocamento.

**Verificar:** consulte `sandbox_stg.stg_gsc_brand`. Não há os 3 últimos dias (preliminares), e os cliques de "tv ao
vivo" não entram. Confira com uma consulta em `sandbox_raw.gsc` filtrando `query like '%ao vivo%'`.

### [ ] 10. `stg_ga4_sessions`: sessionizar o export bruto

**Por quê:** é o ponto mais importante e mais fácil de errar. O export do GA4 tem **uma linha por evento**, não por
sessão. Armadilhas:
- `traffic_source.medium` é o **first touch do usuário**, não o meio da sessão. O meio da sessão vem de `event_params`.
- `events_*` também casa `events_intraday_*` e duplicaria o dia corrente: filtrar `_table_suffix` por 8 dígitos.
- Consentimento negado chega sem `user_pseudo_id`: não dá para montar a sessão, então essas linhas ficam de fora.
- Janela com `current_date()` não é reproduzível: usar uma variável.

**Fazer:**
1. Em `dbt_project.yml`, em `vars:`, acrescente (limita as tabelas lidas, e portanto o custo):
   ```yaml
     ga4_start_date: "20200101"
   ```
2. Crie `dbt/models/staging/stg_ga4_sessions.sql`:
   ```sql
   -- Uma linha por sessão. O export do GA4 tem uma linha por EVENTO, então
   -- a sessão é (user_pseudo_id, ga_session_id), lida de event_params.
   with events as (
       select
           parse_date('%Y%m%d', event_date) as date,
           user_pseudo_id,
           event_name,
           geo.country as country,
           (select value.int_value from unnest(event_params) where key = 'ga_session_id') as ga_session_id,
           (select value.string_value from unnest(event_params) where key = 'medium') as medium
       from {{ source('ga4', 'events') }}
       where regexp_contains(_table_suffix, r'^\d{8}$')               -- exclui events_intraday_*
         and _table_suffix >= '{{ var("ga4_start_date") }}'           -- limita os dias lidos (custo)
   )

   select
       date,
       user_pseudo_id,
       ga_session_id,
       max(medium) as medium,                          -- o meio da sessão vem do evento, não de traffic_source
       max(country) as country,
       logical_or(event_name = 'first_visit') as is_new_user
   from events
   -- sem user_pseudo_id (consentimento negado) não há como montar a sessão
   where user_pseudo_id is not null
     and ga_session_id is not null
   group by date, user_pseudo_id, ga_session_id
   ```
   Entenda `unnest(event_params)`: cada evento carrega uma lista de pares chave/valor; a subconsulta pega o valor da
   chave `ga_session_id` (e de `medium`).
3. `dbt run --select stg_ga4_sessions`

**Verificar:** consulte sessões por meio e por dia. Há dias com um pico de tráfego direto (14/08 e 19/09): são bots,
com país EUA e sem `first_visit`. Confirme com
`select country, count(*) from sandbox_stg.stg_ga4_sessions where date = '2026-08-14' group by 1`.

### [ ] 11. `dim_date`: a espinha do calendário

**Por quê:** os marts juntam fontes com fusos e atrasos diferentes (menções em UTC, GA4 em Brasília, GSC no Pacífico).
Sem um calendário único, `JOIN` por data cria buracos e duplicatas silenciosas. Regra: **todas as fontes viram data de
Brasília** antes de entrar nos marts (o `stg_mentions` já fez isso no passo 6).

**Fazer:** crie `dbt/models/intermediate/dim_date.sql`:
```sql
-- Calendário diário contínuo: todos os marts juntam nele, então um dia sem dado vira linha com zero/nulo
-- em vez de sumir.
select date
from unnest(generate_date_array(
    (select min(date) from {{ ref('stg_mentions') }}),
    (select max(date) from {{ ref('stg_mentions') }})
)) as date
```
Adicione ao `schema.yml`:
```yaml
  - name: dim_date
    columns:
      - name: date
        tests: [unique, not_null]
```
`dbt run --select dim_date` e `dbt test --select dim_date`.

**Verificar:** testes verdes e uma linha por dia, sem lacunas.

### [ ] 12. Camada intermediária: `int_mentions_labeled` e `int_ga4_daily`

**Por quê:** a camada intermediária junta e enriquece sem ainda responder a uma pergunta de negócio. Em
`int_mentions_labeled` entra o `LEFT JOIN` com os rótulos do NLP: menções ainda **sem rótulo** (fila de classificação)
precisam continuar aparecendo. Em `int_ga4_daily`, sessões viram contagens por dia.

**Fazer:**
1. Crie `dbt/models/intermediate/int_mentions_labeled.sql`:
   ```sql
   -- Menções com o rótulo do NLP. LEFT JOIN: menção ainda sem rótulo continua na tabela.
   with labels as (
       select source, mention_id, sentiment, sentiment_score, topic, intent
       from {{ source('raw', 'mention_labels') }}
       qualify row_number() over (partition by source, mention_id order by classified_at desc) = 1
   )

   select
       m.*,
       l.sentiment,
       l.sentiment_score,
       l.topic,
       l.intent
   from {{ ref('stg_mentions') }} as m
   left join labels as l
       on m.source = l.source
      and m.mention_id = l.mention_id
   ```
   O join é por `(source, mention_id)`, sem a data: a data UTC do rótulo pode diferir da data de Brasília da menção.
2. Crie `dbt/models/intermediate/int_ga4_daily.sql`:
   ```sql
   -- Sessões por dia, só tráfego do Brasil. Os picos de bot (tráfego direto dos EUA) ficam de fora.
   select
       date,
       count(*) as sessions,
       countif(medium = '(none)') as direct_sessions,
       countif(is_new_user) as new_users
   from {{ ref('stg_ga4_sessions') }}
   where country = 'Brazil'
   group by date
   ```
3. Adicione ao `schema.yml`:
   ```yaml
     - name: int_mentions_labeled
       tests:
         - dbt_utils.equal_rowcount:         # o LEFT JOIN não pode duplicar nem perder menções
             compare_model: ref('stg_mentions')
       columns:
         - name: sentiment
           tests:
             - accepted_values:
                 values: [positive, neutral, negative]
                 config: {where: "sentiment is not null"}
   ```
4. `dbt build --select int_mentions_labeled int_ga4_daily` (o `build` roda modelos e testes juntos).

**Verificar:** testes verdes. Em `int_ga4_daily`, os picos de 14/08 e 19/09 sumiram.

---

## Parte D. Marts (as respostas de negócio)

### [ ] 13. `mart_daily_brand_health`

**Por quê:** a tabela central, **uma linha por dia**: menções, share of voice, net sentiment, cliques de marca,
sessões diretas, Trends. É o que alimenta o painel.

**Fazer:** crie `dbt/models/marts/mart_daily_brand_health.sql`:
```sql
-- Tabela central: UMA linha por dia (data de Brasília).
with mentions as (
    select
        date,
        count(*) as mentions_total,
        countif(query_group = 'marca') as mentions_brand,
        countif(query_group = 'marca' and sentiment is not null) as mentions_brand_labeled,
        countif(query_group = 'marca' and sentiment = 'positive') as mentions_brand_positive,
        countif(query_group = 'marca' and sentiment = 'negative') as mentions_brand_negative,
        sum(if(query_group = 'marca', coalesce(engagement, 0), 0)) as engagement_brand
    from {{ ref('int_mentions_labeled') }}
    group by date
),

trends as (
    select date, max(interest) as trends_brand
    from {{ source('raw', 'trends_daily') }}
    where term = '{{ var("brand_term") }}'
    group by date
)

select
    d.date,
    coalesce(m.mentions_brand, 0) as mentions_brand,
    coalesce(m.mentions_total, 0) as mentions_total,
    safe_divide(m.mentions_brand, m.mentions_total) as share_of_voice,
    -- denominador = menções da marca já rotuladas (as sem rótulo puxariam o índice para 0)
    safe_divide(m.mentions_brand_positive - m.mentions_brand_negative, m.mentions_brand_labeled) as net_sentiment,
    coalesce(m.mentions_brand_negative, 0) as mentions_brand_negative,
    coalesce(m.engagement_brand, 0) as engagement_brand,
    g.brand_clicks,
    g.brand_impressions,
    ga.sessions,
    ga.direct_sessions,
    ga.new_users,
    t.trends_brand
from {{ ref('dim_date') }} as d
left join mentions as m using (date)
left join {{ ref('stg_gsc_brand') }} as g using (date)
left join {{ ref('int_ga4_daily') }} as ga using (date)
left join trends as t using (date)
```
Note o **grão**: a base é `dim_date`, e tudo entra com `LEFT JOIN`. Dia sem dado de uma fonte fica `null` naquela coluna,
sem sumir do mart. Adicione ao `schema.yml`:
```yaml
  - name: mart_daily_brand_health
    columns:
      - name: date
        tests: [unique, not_null]
```
`dbt build --select mart_daily_brand_health`

**Verificar:** testes verdes; `select * from sandbox_mart.mart_daily_brand_health order by date desc limit 10`. Os 3
últimos dias têm `brand_clicks` nulo (GSC preliminar), e é o esperado.

### [ ] 14. `mart_sov_weekly`, `mart_topics_sentiment`, `mart_crisis_alerts`

**Por quê:** cada uma responde a uma linha da tabela "sinal → decisão" de `CLAUDE.md` (mídia, conteúdo, produto).

**Fazer:** crie os três arquivos em `dbt/models/marts/`.

`mart_sov_weekly.sql`:
```sql
-- Share of voice por semana: menções do grupo ÷ menções de todos os grupos.
select
    date_trunc(date, week(monday)) as week,
    query_group,
    count(*) as mentions,
    safe_divide(count(*), sum(count(*)) over (partition by date_trunc(date, week(monday)))) as share_of_voice
from {{ ref('int_mentions_labeled') }}
group by week, query_group
```

`mart_topics_sentiment.sql`:
```sql
-- Net sentiment e engajamento por tema e semana, só para a marca.
select
    date_trunc(date, week(monday)) as week,
    topic,
    count(*) as mentions,
    safe_divide(countif(sentiment = 'positive') - countif(sentiment = 'negative'), count(*)) as net_sentiment,
    avg(coalesce(engagement, 0)) as avg_engagement
from {{ ref('int_mentions_labeled') }}
where query_group = 'marca'
  and topic is not null
group by week, topic
```

`mart_crisis_alerts.sql`:
```sql
-- Dia de crise: menções negativas acima de 2 desvios-padrão da média dos 28 dias anteriores.
with d as (
    select
        date,
        mentions_brand_negative as neg,
        avg(mentions_brand_negative) over w as mu,
        stddev(mentions_brand_negative) over w as sd,
        count(*) over w as days_in_window
    from {{ ref('mart_daily_brand_health') }}
    window w as (order by date rows between 28 preceding and 1 preceding)
)

select date, neg, mu, sd, safe_divide(neg - mu, sd) as z_score
from d
where days_in_window >= 14                      -- sem histórico suficiente o z-score não vale
  and safe_divide(neg - mu, sd) > 2
```
A janela `28 preceding and 1 preceding` exclui o próprio dia: ele não pode entrar na média com que é comparado.

`dbt build --select mart_sov_weekly mart_topics_sentiment mart_crisis_alerts`

**Verificar:** a janela de crise sintética (30/09 a 02/10) aparece em `mart_crisis_alerts`. Se não aparecer, investigue
junto com a coluna `mentions_brand_negative` do mart diário.

### [ ] 15. `mart_lag_correlation` e `mart_campaign_impact`

**Por quê:** são os dois marts com mais risco de **conclusão errada**.
- **Correlação defasada:** com ~150 dias e 15 lags, o maior valor de puro ruído já passa de 0,2. O mart traz o **n de
  dias** e é correlação, não causa.
- **Impacto de campanha:** compara a média diária antes, durante e depois de cada campanha. As campanhas também movem
  buscas e feriados, então não prova causa: isso é o Projeto 3.

**Fazer:** crie os dois arquivos em `dbt/models/marts/`.

`mart_lag_correlation.sql`:
```sql
-- Correlação entre menções num dia e cliques de marca `lag_days` depois.
-- É correlação, não causa. Leia junto com n_days.
select
    lag_days,
    corr(a.mentions_brand, b.brand_clicks) as correlation,
    countif(b.brand_clicks is not null) as n_days
from unnest(generate_array(0, 14)) as lag_days
cross join {{ ref('mart_daily_brand_health') }} as a
join {{ ref('mart_daily_brand_health') }} as b
    on b.date = date_add(a.date, interval lag_days day)
group by lag_days
```

`mart_campaign_impact.sql`:
```sql
-- Média diária antes (7 dias), durante e depois (7 dias) de cada campanha.
with windows as (
    select
        c.campaign_id,
        c.name,
        c.channel,
        c.objective,
        h.mentions_brand,
        h.brand_clicks,
        case
            when h.date between date_sub(c.start_date, interval 7 day) and date_sub(c.start_date, interval 1 day) then 'before'
            when h.date between c.start_date and c.end_date then 'during'
            when h.date between date_add(c.end_date, interval 1 day) and date_add(c.end_date, interval 7 day) then 'after'
        end as period
    from {{ ref('campaign_calendar') }} as c
    cross join {{ ref('mart_daily_brand_health') }} as h
)

select
    campaign_id, name, channel, objective,
    avg(if(period = 'before', mentions_brand, null)) as mentions_before,
    avg(if(period = 'during', mentions_brand, null)) as mentions_during,
    avg(if(period = 'after', mentions_brand, null)) as mentions_after,
    avg(if(period = 'before', brand_clicks, null)) as brand_clicks_before,
    avg(if(period = 'during', brand_clicks, null)) as brand_clicks_during,
    avg(if(period = 'after', brand_clicks, null)) as brand_clicks_after
from windows
where period is not null
group by campaign_id, name, channel, objective
```

`dbt build --select mart_lag_correlation mart_campaign_impact`

**Verificar com os dois cenários.** Rode os passos acima no cenário `realistic` e depois recarregue o sandbox com
`python -m scripts.load_synthetic --scenario lag3` e `dbt build`. No `lag3` a correlação máxima deve cair no lag 3
(≈ 0,86); no `realistic` nenhum lag se destaca e o lag 0 mostra correlação sem causa (as campanhas são confundidor).
Se o SQL acerta o `lag3`, ele está correto. Detalhes em `docs/DADOS_SINTETICOS.md`.

---

## Parte E. Operar

### [ ] 16. Documentação e linhagem

**Por quê:** `dbt docs` gera um site com o DAG: mostra de onde cada coluna vem, útil para o portfólio.
**Fazer:** descreva modelos e colunas no `schema.yml` (campo `description:`); depois `dbt docs generate && dbt docs serve`.

### [ ] 17. Rodar de forma seletiva e controlar custo

- `dbt build` = seeds + modelos + testes na ordem do DAG. `dbt build --select +mart_daily_brand_health`: o modelo e tudo
  o que ele depende. `dbt ls` lista o que seria executado.
- `--full-refresh` recria tabelas incrementais do zero.
- **Materialization:** `view` (barato, recalcula a cada consulta), `table` (guarda; bom para marts), `incremental`
  (processa só o novo; útil se o GA4 crescer). Nosso volume é pequeno: comparar custo antes de complicar.
- Conferir o custo de uma consulta no BigQuery antes de rodar, e respeitar `maximum_bytes_billed`.

### [ ] 18. Dev e prod

**Por quê:** o mesmo código roda em dois lugares. No `profiles.yml`, dois *targets*: `dev` (datasets `sandbox_*`) e `prod`
(datasets `raw`, `stg`, `int`, `mart`, só quando houver dado real). Use `dbt/profiles.yml.example` como modelo do
`prod`. `dbt build --target prod` muda o destino sem mudar o código.

### [ ] 19. CI e agendamento

**Fazer:** `dbt parse` e `dbt build` num ambiente de teste a cada pull request (usa credencial do CI, nunca no repositório);
depois o agendamento da Fase 4 (coletores → classify → `dbt build` → alerta).

---

## Glossário rápido

| Termo | Significado |
|---|---|
| DAG | grafo de dependências entre modelos, montado pelos `ref()` e `source()` |
| grão | o que representa **uma linha** de um modelo (ex.: 1 dia, 1 sessão) |
| staging | primeira camada sobre o raw: renomeia, tipa, deduplica |
| mart | tabela final, uma por pergunta de negócio |
| compilar | transformar Jinja em SQL puro (`target/compiled/`) |
| materialization | como o `SELECT` é persistido |
| idempotente | rodar duas vezes dá o mesmo resultado |
