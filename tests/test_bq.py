from unittest.mock import MagicMock, patch

import pytest

from src.common import bq


def _row(mid, text="a"):
    return {"source": "x", "mention_id": mid, "published_at": "2026-01-01T00:00:00+00:00",
            "date": "2026-01-01", "text": text, "author_hash": None, "url": None, "query_group": "marca",
            "language": None, "engagement": None, "reach": None, "metrics": "{}",
            "_loaded_at": "2026-01-01T00:00:00+00:00"}


def test_upsert_empty_does_not_touch_bq():
    with patch.object(bq.bigquery, "Client") as client:
        assert bq.upsert("mentions", []) == 0
        client.assert_not_called()


def test_dedupe_keeps_last_per_natural_key():
    out = bq._dedupe("mentions", [_row("1", "velho"), _row("2"), _row("1", "novo")])
    assert len(out) == 2
    assert {r["text"] for r in out if r["mention_id"] == "1"} == {"novo"}


def test_upsert_merges_on_natural_key_and_drops_staging():
    client = MagicMock()
    with patch.object(bq.bigquery, "Client", return_value=client):
        n = bq.upsert("mentions", [_row("1"), _row("1", "novo")])
    assert n == 1
    sql = client.query.call_args.args[0]
    assert sql.startswith("MERGE")
    assert "t.source = s.source AND t.mention_id = s.mention_id AND t.date = s.date" in sql
    assert "WHEN NOT MATCHED THEN INSERT ROW" in sql
    client.delete_table.assert_called_once()


def test_upsert_drops_staging_even_on_failure():
    client = MagicMock()
    client.query.side_effect = RuntimeError("boom")
    with patch.object(bq.bigquery, "Client", return_value=client):
        with pytest.raises(RuntimeError):
            bq.upsert("mentions", [_row("1")])
    client.delete_table.assert_called_once()


def test_every_table_has_keys_inside_schema():
    for table, keys in bq.KEYS.items():
        cols = {f.name for f in bq.SCHEMAS[table]}
        assert set(keys) <= cols
