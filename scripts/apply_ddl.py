"""Aplica os DDLs de sql/ddl/ no BigQuery. Uso: python -m scripts.apply_ddl [--dry-run]"""
import sys
from pathlib import Path

from google.cloud import bigquery

from src.common.config import settings


def render(sql: str) -> str:
    p = settings.bq_dataset_prefix
    return (sql.replace("${PROJECT}", settings.gcp_project)
               .replace("${RAW}", f"{p}raw").replace("${STG}", f"{p}stg")
               .replace("${INT}", f"{p}int").replace("${MART}", f"{p}mart")
               .replace("${LOCATION}", settings.bq_location))


def main(dry_run: bool = False) -> None:
    client = None if dry_run else bigquery.Client(project=settings.gcp_project, location=settings.bq_location)
    for path in sorted(Path("sql/ddl").glob("*.sql")):
        sql = render(path.read_text(encoding="utf-8"))
        print(f"-- {path.name}")
        if dry_run:
            print(sql)
        else:
            client.query(sql).result()
            print("ok")


if __name__ == "__main__":
    main(dry_run="--dry-run" in sys.argv)
