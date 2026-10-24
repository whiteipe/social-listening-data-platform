from datetime import datetime, timedelta, timezone

from src.common.schema import hash_author, make_row


def test_hash_author_none():
    assert hash_author(None, "s") is None
    assert hash_author("", "s") is None


def test_hash_author_deterministic_and_salted():
    assert hash_author("abc", "s1") == hash_author("abc", "s1")
    assert hash_author("abc", "s1") != hash_author("abc", "s2")
    assert "abc" not in hash_author("abc", "s1")
    assert len(hash_author("abc", "s1")) == 16


def test_make_row_converts_to_utc_and_date():
    brt = timezone(timedelta(hours=-3))
    row = make_row(source="x", mention_id=1, published_at=datetime(2026, 1, 1, 22, 0, tzinfo=brt),
                   text="  oi  ", url=None, query_group="marca", author_id="u1", salt="s")
    assert row["published_at"].startswith("2026-01-02T01:00:00")
    assert row["date"] == "2026-01-02"
    assert row["text"] == "oi"
    assert row["mention_id"] == "1"
    assert row["author_hash"] != "u1"
    assert row["metrics"] == "{}"


def test_make_row_naive_datetime_assumed_utc():
    row = make_row(source="x", mention_id="1", published_at=datetime(2026, 1, 1, 12, 0),
                   text=None, url=None, query_group="marca")
    assert row["date"] == "2026-01-01"
    assert row["text"] == ""
