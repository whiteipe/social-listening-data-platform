-- Um dataset por camada: raw (Python grava), stg, int e mart (dbt grava).
CREATE SCHEMA IF NOT EXISTS `${PROJECT}.${RAW}` OPTIONS (location = '${LOCATION}');
CREATE SCHEMA IF NOT EXISTS `${PROJECT}.${STG}` OPTIONS (location = '${LOCATION}');
CREATE SCHEMA IF NOT EXISTS `${PROJECT}.${INT}` OPTIONS (location = '${LOCATION}');
CREATE SCHEMA IF NOT EXISTS `${PROJECT}.${MART}` OPTIONS (location = '${LOCATION}');
