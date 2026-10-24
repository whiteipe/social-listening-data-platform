from __future__ import annotations

import uuid

from google.cloud import bigquery

from .config import settings

F = bigquery.SchemaField
SCHEMAS = {
    "mentions": [F("source", "STRING", "REQUIRED"), F("mention_id", "STRING", "REQUIRED"),
                 F("published_at", "TIMESTAMP", "REQUIRED"), F("date", "DATE", "REQUIRED"),
                 F("text", "STRING"), F("author_hash", "STRING"), F("url", "STRING"),
                 F("query_group", "STRING"), F("language", "STRING"),
                 F("engagement", "INT64"), F("reach", "INT64"), F("metrics", "STRING"),
                 F("_loaded_at", "TIMESTAMP", "REQUIRED")],
    "social_daily": [F("date", "DATE", "REQUIRED"), F("platform", "STRING", "REQUIRED"),
                     F("metric", "STRING", "REQUIRED"), F("value", "FLOAT64"),
                     F("_loaded_at", "TIMESTAMP", "REQUIRED")],
    "trends_daily": [F("date", "DATE", "REQUIRED"), F("term", "STRING", "REQUIRED"),
                     F("geo", "STRING", "REQUIRED"), F("interest", "INT64"),
                     F("_loaded_at", "TIMESTAMP", "REQUIRED")],
    "mention_labels": [F("source", "STRING", "REQUIRED"), F("mention_id", "STRING", "REQUIRED"),
                       F("date", "DATE", "REQUIRED"), F("sentiment", "STRING"),
                       F("sentiment_score", "FLOAT64"), F("topic", "STRING"),
                       F("intent", "STRING"), F("model_version", "STRING"),
                       F("classified_at", "TIMESTAMP", "REQUIRED")],
}
KEYS = {
    "mentions": ["source", "mention_id", "date"],
    "social_daily": ["date", "platform", "metric"],
    "trends_daily": ["date", "term", "geo"],
    "mention_labels": ["source", "mention_id", "date"],
}


def _dedupe(table: str, rows: list[dict]) -> list[dict]:
    """MERGE falha se a origem tiver chaves duplicadas; mantém a última ocorrência."""
    by_key = {tuple(r[k] for k in KEYS[table]): r for r in rows}
    return list(by_key.values())


def upsert(table: str, rows: list[dict]) -> int:
    """Carrega em tabela temporária e faz MERGE. Reexecutar não duplica."""
    if not rows:
        return 0
    rows = _dedupe(table, rows)
    client = bigquery.Client(project=settings.gcp_project, location=settings.bq_location)
    dataset = f"{settings.gcp_project}.{settings.bq_dataset}"
    staging = f"{dataset}._stg_{table}_{uuid.uuid4().hex[:8]}"
    try:
        client.load_table_from_json(
            rows, staging,
            job_config=bigquery.LoadJobConfig(schema=SCHEMAS[table], write_disposition="WRITE_TRUNCATE"),
        ).result()
        cols = [f.name for f in SCHEMAS[table]]
        on = " AND ".join(f"t.{k} = s.{k}" for k in KEYS[table])
        upd = ", ".join(f"t.{c} = s.{c}" for c in cols if c not in KEYS[table])
        sql = (f"MERGE `{dataset}.{table}` t USING `{staging}` s ON {on} "
               f"WHEN MATCHED THEN UPDATE SET {upd} WHEN NOT MATCHED THEN INSERT ROW")
        client.query(sql).result()
    finally:
        client.delete_table(staging, not_found_ok=True)
    return len(rows)
