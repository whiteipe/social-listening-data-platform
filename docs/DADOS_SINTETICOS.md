# Dados sintéticos

Gerados por script (`python -m scripts.synthetic_data`), nunca escritos à mão. Saída só em arquivos locais
(`data/synthetic/<cenário>/`, ignorado pelo git); **nada é gravado no BigQuery**. Tudo é marcado como sintético:
`mention_id` com `synthetic`, URLs `synthetic.invalid`, `is_synthetic = true` em GSC/GA4/campanhas,
`model_version = synthetic-generator` nos labels.

Mesmo `--seed` e `--as-of` produzem exatamente os mesmos dados (padrão: seed 42, as-of 2026-10-24, janela de 120 dias).

## Cenários

| Cenário | Para quê | Como é feito |
|---|---|---|
| `realistic` | exercitar o pipeline com as dificuldades reais | Menções e buscas compartilham só calendário, feriados e campanhas. Sem acoplamento causal. |
| `lag3` | provar que a SQL de correlação defasada recupera um lag conhecido | Busca de marca = função das menções de 3 dias antes, mais ruído. **Não é achado de negócio.** |

## Dificuldades reproduzidas

| Dificuldade | Parâmetro | Onde |
|---|---|---|
| Fuso | menções em UTC; GA4 no horário de Brasília; GSC no Pacífico (12% dos cliques da madrugada caem no dia anterior) | `GSC_PT_SPILL` |
| Atraso e revisão do GSC | último dia disponível = hoje − 2; 3 últimos dias preliminares com 70% do valor | `GSC_LAG_DAYS`, `GSC_PRELIM_*` |
| Queries anônimas | 25% dos cliques do GSC sem texto de query | `GSC_ANON_SHARE` |
| Consentimento no GA4 | 22% das sessões com consentimento negado; novos usuários subcontados | `GA4_DENIED_SHARE` |
| Lacunas | coleta de menções falha em 02/09; tag do GA4 cai em 28 e 29/08 | `COLLECTION_GAP`, `GA4_OUTAGE` |
| Bots | sessões diretas multiplicadas por 6 em 14/08 e 19/09, sem novos usuários | `BOT_DAYS` |
| Sazonalidade e feriados | fim de semana 60% a 80% da base; feriados 75% | `WEEKDAY`, `HOLIDAYS` |
| Confundidores | campanhas movem menções e buscas ao mesmo tempo | `CAMPAIGNS` |
| Crise | 30/09 a 02/10: volume 2,5x, 70% negativas, tema atendimento/defeito | `CRISIS` |
| Ruído de regex | queries como "tv ao vivo" casam com a marca (`vivo`) | `NOISE_QUERIES` |
| Trends | relativo 0 a 100 (renormalizado pelo termo mais forte), sem o dia parcial | `_gen_trends` |
| Duplicidade | menções com mesmo id reaparecem com data UTC deslocada (exercita o dedupe) | `_gen_mentions` |
| Rótulos pendentes | 88% das menções classificadas; só 40% nas mais recentes | `LABELED_SHARE*` |

## Formato

- `mentions`, `mention_labels`, `trends_daily`, `social_daily`: **idênticos às tabelas raw** (`src/common/bq.py`);
  um teste valida colunas e campos obrigatórios.
- `gsc`: uma linha por `data_date`, `query`, com `clicks`, `impressions`, `is_anonymized_query`, `data_state`.
  Formato simplificado do export `searchdata_site_impression`.
- `ga4`: uma linha por `event_date`, `event_name`, `traffic_medium`, `consent_state`, com `event_count`.
  Formato **simplificado**: o export real tem uma linha por evento com colunas aninhadas. O modelo de staging do dbt
  terá de ser ajustado a uma das duas formas (decisão pendente, a tomar junto com o dbt).
- `campaign_calendar.csv`: as 3 campanhas sintéticas, com a mesma forma do seed do dbt.

## O que os testes garantem (`tests/test_synthetic_data.py`)

- Schema e determinismo; tudo sinalizado como sintético; nenhum identificador de aparência real.
- GSC com atraso, linhas preliminares e cliques anônimos; GA4 com consentimento, lacuna e pico de bot.
- A lacuna de coleta é um dia de **Brasília**, não de UTC (as menções das 21h às 24h do dia anterior caem no dia).
- `lag3`: a correlação defasada atinge o máximo no lag 3 (0,86 com a semente 42).
- `realistic`: sem sinal no lag 3, mas **correlação em lag 0 sem causa** (campanhas e feriados são confundidores) e
  maior |correlação| de ruído acima de 0,2 entre 15 lags. Isso ilustra o risco de comparações múltiplas.

Os limites desses testes foram fixados depois de ver os números do gerador; descrevem o comportamento medido,
não uma meta definida antes.

## Limites e uso correto

- **Volume irreal frente ao coletor real:** a marca recebe ~14 menções/dia no sintético; o YouTube real entrega
  poucas por dia. Resultados estatísticos do sintético não preveem a precisão que teremos com dado real.
- **Rótulos perfeitos:** o sentimento sintético segue o texto por construção. **Não usar para o bake-off de
  classificadores** (Laya, JEV, baseline): ele exige rótulos humanos de texto real.
- **Eventos com datas fixas de 2026:** com outro `--as-of` fora da janela, as campanhas, a crise e as lacunas
  saem do período.
- O gerador é um modelo simples (Poisson com ruído AR(1)): não captura memes, viralização, bots coordenados
  nem sazonalidade anual.
