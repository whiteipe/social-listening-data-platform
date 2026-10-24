-- Dataset único: raw, stg, int e mart convivem por prefixo de tabela.
-- Tabelas raw mantêm o nome (mentions, social_daily, trends_daily, mention_labels).
CREATE SCHEMA IF NOT EXISTS `${PROJECT}.${DATASET}`
OPTIONS (location = '${LOCATION}');
