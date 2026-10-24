-- Menções públicas de qualquer fonte (formato único)
CREATE TABLE IF NOT EXISTS `${PROJECT}.${DATASET}.mentions` (
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
CREATE TABLE IF NOT EXISTS `${PROJECT}.${DATASET}.social_daily` (
  date        DATE   NOT NULL,
  platform    STRING NOT NULL,       -- instagram | youtube | gdelt
  metric      STRING NOT NULL,       -- reach | views | subscribers | news_tone:marca ...
  value       FLOAT64,
  _loaded_at  TIMESTAMP NOT NULL
)
PARTITION BY date;

-- Google Trends (interesse relativo 0-100)
CREATE TABLE IF NOT EXISTS `${PROJECT}.${DATASET}.trends_daily` (
  date        DATE   NOT NULL,
  term        STRING NOT NULL,
  geo         STRING NOT NULL,
  interest    INT64,
  _loaded_at  TIMESTAMP NOT NULL
)
PARTITION BY date;

-- Resultado do NLP (um registro por menção)
CREATE TABLE IF NOT EXISTS `${PROJECT}.${DATASET}.mention_labels` (
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
