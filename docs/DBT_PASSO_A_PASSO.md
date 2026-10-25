# dbt passo a passo: do zero até os marts

Guia para aprender dbt construindo este projeto. Cada passo tem **Por quê**, **Fazer** e **Verificar**.
Fazemos juntos: eu mostro o comando e o motivo, você roda ou me pede para rodar, e perguntamos o que surgir.
Marque os passos concluídos em `[ ]`.

Comandos assumem Git Bash na raiz do repositório com o ambiente ativado (`source .venv/Scripts/activate`).

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
| **materialization** | como o `SELECT` vira objeto: `view`, `table`, `incremental` | staging = view, marts = table |
| **test** | afirmação sobre os dados (`unique`, `not_null`...) | chaves únicas, valores aceitos |
| **seed** | CSV pequeno versionado, carregado como tabela | `campaign_calendar` |
| **macro** | função Jinja reutilizável | `generate_schema_name` |

**Verificar:** você consegue explicar por que a coleta (Python) e a transformação (dbt) ficam separadas.

### [ ] 2. Ambiente e conexão

**Por quê:** o dbt precisa saber *onde* rodar (projeto, dataset, localização). Isso fica em `profiles.yml`, **fora do
repositório**, porque descreve a máquina de quem roda (e pode ter credenciais).

**Fazer:**
1. **Versão estável fixada (feito).** O ambiente tinha vindo com `dbt-core 1.13.0b1` (beta). Agora `requirements.txt` fixa
   `dbt-core==1.12.6` e `dbt-bigquery==1.12.1`; `dbt --version` mostra "Up to date".
2. **Decisão: onde rodar os testes.** Recomendo um dataset separado, `social_listening_sandbox`:
   o dbt cria e apaga objetos à vontade e não toca o dataset real, que fica para dado real. Ver "Dev e prod" no passo 18.
3. Criar `~/.dbt/profiles.yml` a partir de `dbt/profiles.yml.example`, com `method: oauth` (usa o login do `gcloud`),
   `dataset: social_listening_sandbox`, `location: US` e **`maximum_bytes_billed: 1000000000`** (1 GB).
   Essa trava faz o BigQuery recusar consultas que leriam mais que isso: proteção barata contra um erro de custo.
4. `cd dbt && dbt debug`.

**Verificar:** `dbt debug` termina com `All checks passed!`.

### [ ] 3. Estrutura do projeto

**Por quê:** saber o que cada arquivo faz evita mexer no lugar errado.

```
dbt/
├── dbt_project.yml        # nome, caminhos, variáveis, materialization por pasta
├── packages.yml           # dependências (dbt_utils)
├── macros/                # generate_schema_name.sql: tudo cai num dataset só
├── seeds/                 # campaign_calendar.csv
└── models/
    ├── sources.yml        # declara o raw
    ├── schema.yml         # testes e documentação
    ├── staging/           # 1 modelo por fonte: limpa tipos, nomes, dedupe
    ├── intermediate/      # junta e enriquece
    └── marts/             # tabelas finais, uma por pergunta de negócio
```

**Por quê do macro:** por padrão o dbt cria um dataset por camada (`stg`, `mart`). Nós queremos **um dataset só**, com
prefixos nos nomes (`stg_`, `int_`, `mart_`). O macro `generate_schema_name` força isso.

**Fazer:** há rascunhos não commitados em `dbt/` (de um agente que parei). Vamos **reconstruir passo a passo** em vez de
herdá-los: eu os movo para uma pasta fora do repositório (nada é apagado) e você os usa só para comparar depois.

**Verificar:** `git status` mostra `dbt/` limpo, e `dbt parse` roda sem erro com os modelos vazios.

---

## Parte B. Dados e o primeiro modelo

### [ ] 4. Carregar os dados sintéticos no sandbox

**Por quê:** o dbt só transforma o que já existe. Precisamos do "L" (load) fora dele.
É o mesmo que o Python fará com os dados reais, mas aqui lemos os arquivos de `data/synthetic/`.

**Fazer:** `scripts/load_synthetic.py` (escrevemos juntos): cria o dataset sandbox, carrega as 4 tabelas raw com o schema
de `src/common/bq.py`, o GSC, e **uma tabela por dia** do GA4 (`events_20260528`, `events_20260529`...) com
`data/synthetic/<cenário>/ga4/schema.json`. O GA4 real também é fragmentado por dia, e é por isso que o dbt o lê com
curinga (`events_*`).

**Verificar:** no console do BigQuery o sandbox tem 4 tabelas raw, o GSC e 149 tabelas `events_*`.
Custo esperado: centavos (alguns MB).

### [ ] 5. Declarar as fontes (`sources`) e a frescura

**Por quê:** `source()` registra de onde o dado vem. Assim o dbt entende a linhagem (o que alimenta o quê) e pode checar
se o dado está **atualizado** (`freshness`), em vez de você descobrir no painel.

**Fazer:** `models/sources.yml` com `raw` (mentions, social_daily, trends_daily, mention_labels), `ga4` (`events_*`) e `gsc`;
`loaded_at_field: _loaded_at` e `freshness: warn_after 36h`. Depois `dbt source freshness`.

**Verificar:** a checagem retorna `PASS` ou `WARN` por tabela. Em dado sintético estático o `WARN` é esperado: o
`_loaded_at` envelhece. Entender por que ele avisa é parte do aprendizado.

### [ ] 6. Primeiro modelo: `stg_mentions`

**Por quê:** é a "camada de limpeza": um modelo por tabela de origem, sem regra de negócio. Um `SELECT` simples já
mostra todo o ciclo do dbt.

**Fazer:**
1. Escrever o `SELECT` com `{{ source('raw', 'mentions') }}`: renomear, filtrar texto vazio, **deduplicar**.
   Atenção: a chave natural no raw é `(source, mention_id, date)`, e a mesma menção pode reaparecer com a data UTC
   deslocada (o gerador simula isso). O README deduplica só por `(source, mention_id)`; vamos ver se isso basta.
2. `dbt run --select stg_mentions`
3. Abrir `target/compiled/.../stg_mentions.sql`: é o SQL que o dbt realmente enviou (Jinja já resolvido).
4. Consultar a view no BigQuery.

**Verificar:** a view existe no sandbox; contagem de linhas = menções únicas esperadas.

### [ ] 7. Testes e o pacote `dbt_utils`

**Por quê:** teste é a razão de usar dbt. Em vez de achar um erro no painel, o `dbt test` falha antes.

**Fazer:**
1. `packages.yml` com `dbt-labs/dbt_utils` e `dbt deps` (instala os pacotes em `dbt_packages/`).
2. `models/schema.yml` para `stg_mentions`: `not_null` em `date`,
   `dbt_utils.unique_combination_of_columns` em `(source, mention_id)`.
3. `dbt test --select stg_mentions`.
4. **Quebre de propósito**: relaxe o dedupe, rode o teste, veja falhar, e conserte. É assim que se aprende a ler a saída.

**Verificar:** testes verdes; você sabe ler o SQL do teste que falhou (`target/compiled/...`).

### [ ] 8. Seeds: `campaign_calendar`

**Por quê:** dados pequenos e estáticos (calendário de campanhas) cabem num CSV versionado: revisão por pull request e
nenhuma carga separada. Mas só para dado de referência, nunca para dado grande.

**Fazer:** `dbt seed`, e conferir a tabela no sandbox. O gerador já escreve `campaign_calendar.csv` com o mesmo formato.

**Verificar:** 3 campanhas sintéticas, com `is_synthetic = true`.

---

## Parte C. Camadas com as dificuldades reais

### [ ] 9. `stg_gsc`: revisão, anônimos e fuso

**Por quê:** o GSC chega com atraso, os últimos dias são **preliminares** (valem ~70%) e parte dos cliques vem sem query.
Tratar errado distorce justamente a série que vamos correlacionar.

**Fazer:** filtrar `data_state = 'final'` (ou marcar preliminares), separar cliques anônimos (`is_anonymized_query`),
aplicar o regex de marca **sem pegar "ao vivo"**, alinhar o dia do Pacífico ao de Brasília.
Cuidado: o GSC pode ter várias versões da mesma `data_date`; guardar a mais recente.

**Verificar:** `brand_clicks` por dia, sem os 3 dias preliminares e sem cliques de "tv ao vivo".

### [ ] 10. `stg_ga4_sessions`: sessionizar o export bruto

**Por quê:** é o ponto mais importante e mais fácil de errar. O export do GA4 tem **uma linha por evento**, não por sessão.
Armadilhas (o SQL original do prompt, em `CLAUDE.md`, errava nelas; já foi corrigido lá):
- `traffic_source.medium` é o **first touch do usuário**, não o meio da sessão. O meio da sessão vem de `event_params`
  (`source`, `medium`) ou de `session_traffic_source_last_click`.
- `or traffic_source.medium is null` contava como "direto" todo evento **sem consentimento** (o campo vem nulo).
- `events_*` também casa `events_intraday_*` e duplicaria o dia corrente: filtrar `_table_suffix` por 8 dígitos.
- Janela com `current_date()` não é reproduzível: usar a variável `ga4_start_date`.

**Fazer:** ler as tabelas fragmentadas com `events_*` filtrando `_TABLE_SUFFIX` (**para o BigQuery ler só os dias
necessários e não gerar custo**); `UNNEST(event_params)` para extrair `ga_session_id` e `medium`; definir a sessão como
`(user_pseudo_id, ga_session_id)`; saída com **uma linha por sessão** (data, meio, novo usuário, consentimento).
Consentimento negado não tem `user_pseudo_id`: contar `session_start` à parte, sem sessionizar.

**Verificar:** sessões por meio por dia batem com o que o gerador produziu (fatores de calendário, pico de bot no 14/08).

### [ ] 11. `dim_date`: a espinha do calendário e o fuso

**Por quê:** os marts juntam fontes com fusos e atrasos diferentes (menções em UTC, GA4 em Brasília, GSC no Pacífico).
Sem um calendário único, `JOIN` por data cria buracos e duplicatas silenciosas.

**Fazer:** um modelo de calendário diário (`GENERATE_DATE_ARRAY`) e a regra: **todas as fontes viram data de Brasília**
antes de entrar nos marts (menções: `DATE(published_at, 'America/Sao_Paulo')`).

**Verificar:** teste `unique` e `not_null` em `date`, sem lacunas.

### [ ] 12. `int_mentions_labeled`

**Por quê:** a camada intermediária junta e enriquece sem ainda responder a uma pergunta de negócio. Aqui entra o
`LEFT JOIN` com os labels do NLP: menções ainda **sem label** (fila de classificação) precisam continuar aparecendo.

**Verificar:** número de linhas = `stg_mentions` (o `LEFT JOIN` não pode duplicar).

---

## Parte D. Marts (as respostas de negócio)

### [ ] 13. `mart_daily_brand_health`

**Por quê:** a tabela central, **uma linha por dia**: menções, share of voice, net sentiment, cliques de marca,
sessões diretas, Trends. É o que alimenta o painel.

**Fazer:** definir o **grão** (1 linha por data de Brasília) e juntar tudo à `dim_date` com `LEFT JOIN`.

**Verificar:** teste `unique` em `date`; 150 linhas.

### [ ] 14. `mart_sov_weekly`, `mart_topics_sentiment`, `mart_crisis_alerts`

**Por quê:** cada uma responde a uma linha da tabela "sinal → decisão" do README (mídia, conteúdo, produto).

**Fazer:** SOV semanal por grupo; net sentiment por tema; alerta de crise (z-score > 2 sobre média de 28 dias).
**Verificar:** a janela de crise sintética (30/09 a 02/10) dispara o alerta.

### [ ] 15. `mart_lag_correlation` e `mart_campaign_impact`

**Por quê:** são os dois marts com mais risco de **conclusão errada**.
- **Correlação defasada:** com ~150 dias e 15 lags, o maior valor de puro ruído já passa de 0,2 (medimos isso no gerador).
  O mart deve trazer o **n de dias** e deixar claro que é correlação, não causa.
- **Impacto de campanha:** o SQL do README faz `CROSS JOIN` sem filtro por campanha; precisa juntar por período.

**Fazer:** implementar os dois e rodar contra **os dois cenários** do gerador.
**Verificar:** no cenário `lag3` o máximo cai no lag 3 (≈ 0,86); no `realistic` nenhum lag se destaca e o lag 0 mostra
correlação sem causa (campanhas são confundidor). Se o SQL acertar o `lag3`, ele está correto.

---

## Parte E. Operar

### [ ] 16. Documentação e linhagem

**Por quê:** `dbt docs` gera um site com o DAG: mostra de onde cada coluna vem, útil para o portfólio.
**Fazer:** descrever modelos e colunas no `schema.yml`; `dbt docs generate && dbt docs serve`.

### [ ] 17. Rodar de forma seletiva e controlar custo

- `dbt build` = seeds + modelos + testes na ordem do DAG. `dbt build --select +mart_daily_brand_health`: o modelo e tudo
  o que ele depende. `dbt ls` lista o que seria executado.
- `--full-refresh` recria tabelas incrementais do zero.
- **Materialization:** `view` (barato, recalcula a cada consulta), `table` (guarda; bom para marts), `incremental`
  (processa só o novo; útil se o GA4 crescer). Nosso volume é pequeno: comparar custo antes de complicar.
- Conferir o custo de uma consulta no BigQuery antes de rodar, e respeitar `maximum_bytes_billed`.

### [ ] 18. Dev e prod

**Por quê:** o mesmo código roda em dois lugares. No `profiles.yml`, dois *targets*: `dev` (sandbox) e `prod`
(`social_listening_data_platform`, só quando houver dado real). `dbt build --target prod` muda o destino sem mudar o código.

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

## Como perguntar

Pergunte a qualquer momento: "por que `ref` e não o nome da tabela?", "o que o `dbt test` rodou?", "mostra o SQL compilado".
Uma boa dúvida é um passo a mais no guia.
