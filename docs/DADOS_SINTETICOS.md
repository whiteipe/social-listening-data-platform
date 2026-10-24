# Dados sintéticos

Gerados por script (`python -m scripts.synthetic_data`), nunca escritos à mão. Saída só em arquivos locais
(`data/synthetic/<cenário>/`, ignorado pelo git); **nada é gravado no BigQuery**. Tudo é marcado como sintético:
`mention_id` com `synthetic`, URLs `synthetic.invalid`, `is_synthetic = true` em GSC/GA4/campanhas,
`model_version = synthetic-generator` nos labels.

Mesmo `--seed` e `--as-of` produzem exatamente os mesmos dados (padrão: seed 42, as-of 2026-10-24, janela de 150 dias).

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
| Consentimento no GA4 | 22% das sessões com `analytics_storage = 'No'`; sem `user_pseudo_id` e sem `ga_session_id` (hipótese, ver abaixo) | `GA4_DENIED_SHARE` |
| `traffic_source` do GA4 | é first touch do **usuário**; para usuário recorrente difere do meio da sessão | `FIRST_TOUCH_MIX` |
| Chegada tardia no GA4 | tabelas dos 3 últimos dias incompletas (5%, 2% e 0,5% dos eventos ausentes) | `LATE_ARRIVAL_MISSING` |
| Bots | sessões diretas multiplicadas por 6 em 14/08 e 19/09: país EUA, sem `first_visit`, sem engajamento | `BOT_DAYS` |
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
- `ga4/events_YYYYMMDD.jsonl.gz`: **export bruto do GA4**, uma tabela por dia (como `events_YYYYMMDD` no BigQuery),
  com os campos aninhados da documentação (`event_params`, `privacy_info`, `device`, `geo`, `traffic_source`,
  `collected_traffic_source`, `session_traffic_source_last_click`...). `ga4/schema.json` é o schema de carga.
  Tipo de evento: `first_visit`, `session_start` e `page_view`. Não há linha de sessão: sessão =
  `(user_pseudo_id, ga_session_id)`. O export real **não tem coluna de sintético**: os dados se identificam por
  hostname `exemplo-sintetico.invalid`, `stream_id` 1000000001 e `user_pseudo_id` iniciando em `SYN`.
  Volume: ~1.150 eventos/dia (≈173 mil em 150 dias, 7 MB comprimidos); as sessões são 25% das calculadas
  (`SESSION_SCALE`) para o arquivo não crescer demais. O GA4 é gerado dia a dia (streaming), não em memória.
- `campaign_calendar.csv`: as 3 campanhas sintéticas, com a mesma forma do seed do dbt.

## O que os testes garantem (`tests/test_synthetic_data.py`)

- Schema e determinismo; tudo sinalizado como sintético; nenhum identificador de aparência real.
- GSC com atraso, linhas preliminares e cliques anônimos.
- GA4: schema da documentação (checagem recursiva de cada coluna), `event_date` em Brasília e `event_timestamp` em UTC, first touch diferente do meio da sessão, consentimento negado sem como sessionizar, pico de bot e tabelas recentes incompletas.
- Janela de 150 dias sem dias faltantes (a falha de coleta foi removida a pedido).
- `lag3`: a correlação defasada atinge o máximo no lag 3 (0,86 com a semente 42).
- `realistic`: sem sinal no lag 3, mas **correlação em lag 0 sem causa** (campanhas e feriados são confundidores) e
  maior |correlação| de ruído acima de 0,2 entre 15 lags. Isso ilustra o risco de comparações múltiplas.

Os limites desses testes foram fixados depois de ver os números do gerador; descrevem o comportamento medido,
não uma meta definida antes.

## Limites e uso correto

- **Volume irreal frente ao coletor real:** a marca recebe ~14 menções/dia no sintético; o YouTube real entrega
  poucas por dia. Resultados estatísticos do sintético não preveem a precisão que teremos com dado real.
- **Hipótese não confirmada na documentação:** o que o GA4 exporta quando o consentimento é negado. A documentação
  não diz; modelei sem `user_pseudo_id` e sem `ga_session_id`. Validar contra um export real antes de confiar.
- **Schema não carregado ainda no BigQuery:** foi validado por testes locais contra a documentação; a carga real ocorrerá
  ao configurarmos o dbt.
- **Rótulos perfeitos:** o sentimento sintético segue o texto por construção. **Não usar para o bake-off de
  classificadores** (Laya, JEV, baseline): ele exige rótulos humanos de texto real.
- **Eventos com datas fixas de 2026:** com outro `--as-of` fora da janela, as campanhas, a crise e os picos de bot
  saem do período.
- **GSC continua em formato simplificado** (o export real `searchdata_site_impression` tem outras colunas); só o GA4 foi levado ao formato bruto.
- O gerador é um modelo simples (Poisson com ruído AR(1)): não captura memes, viralização, bots coordenados
  nem sazonalidade anual.
