import pytest
import responses

from src.collectors import google_news
from src.common import bq

RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel>
<item><title>Vivo Fibra amplia cobertura no Sul - TELETIME News</title>
<link>https://news.google.com/rss/articles/AAA</link><pubDate>Fri, 23 Oct 2026 18:30:00 GMT</pubDate></item>
<item><title>Operadora Vivo e operadora Claro disputam clientes - VEJA</title>
<link>https://news.google.com/rss/articles/BBB</link><pubDate>Sat, 24 Oct 2026 09:00:00 GMT</pubDate></item>
<item><title>Show ao vivo hoje à noite - Portal X</title>
<link>https://news.google.com/rss/articles/CCC</link><pubDate>Sat, 24 Oct 2026 10:00:00 GMT</pubDate></item>
</channel></rss>"""


@pytest.fixture(autouse=True)
def _fast(monkeypatch):
    monkeypatch.setattr(google_news.time, "sleep", lambda s: None)
    monkeypatch.setattr("tenacity.nap.time.sleep", lambda s: None)
    monkeypatch.setattr(google_news, "load_queries", lambda: {"marca": ['"operadora Vivo"']})


@responses.activate
def test_google_news_rows_groups_and_filter():
    responses.add(responses.GET, google_news.BASE, body=RSS, status=200)
    rows = google_news.collect(days=2)
    by_group = {(r["query_group"], r["text"]) for r in rows}
    assert ("marca", "Vivo Fibra amplia cobertura no Sul") in by_group
    assert ("marca", "Operadora Vivo e operadora Claro disputam clientes") in by_group
    assert ("concorrente_a", "Operadora Vivo e operadora Claro disputam clientes") in by_group
    assert not any("ao vivo" in r["text"].lower() for r in rows)  # ruído descartado
    assert all(r["source"] == "news" and r["author_hash"] is None for r in rows)
    r = next(r for r in rows if r["text"].startswith("Vivo Fibra"))
    assert r["date"] == "2026-10-23" and r["published_at"].startswith("2026-10-23T18:30:00")
    assert '"outlet": "TELETIME News"' in r["metrics"]


@responses.activate
def test_google_news_idempotent_keys():
    responses.add(responses.GET, google_news.BASE, body=RSS, status=200)
    first, second = google_news.collect(), google_news.collect()
    assert len(bq._dedupe("mentions", first + second)) == len(first)


@responses.activate
def test_google_news_retries_on_server_error():
    responses.add(responses.GET, google_news.BASE, status=503)
    responses.add(responses.GET, google_news.BASE, body=RSS, status=200)
    assert google_news.collect()
    assert len(responses.calls) == 2


def test_split_title():
    assert google_news._split_title("Título - Veículo") == ("Título", "Veículo")
    assert google_news._split_title("Sem veículo") == ("Sem veículo", None)


@responses.activate
def test_google_news_loose_match_applies_only_to_searched_group():
    body = RSS.replace("</channel>", (
        "<item><title>Vivo anuncia 5G em mais cidades - Tecnoblog</title><link>https://news.google.com/rss/articles/DDD</link>"
        "<pubDate>Sat, 24 Oct 2026 11:00:00 GMT</pubDate></item>"
        "<item><title>TIM anuncia plano novo - Tecnoblog</title><link>https://news.google.com/rss/articles/EEE</link>"
        "<pubDate>Sat, 24 Oct 2026 11:00:00 GMT</pubDate></item></channel>"))
    responses.add(responses.GET, google_news.BASE, body=body, status=200)
    got = {(r["query_group"], r["text"]) for r in google_news.collect()}
    assert ("marca", "Vivo anuncia 5G em mais cidades") in got   # busca do grupo marca: regex solto vale
    assert not any(t.startswith("TIM anuncia") for _, t in got)  # TIM não é o grupo buscado


@responses.activate
def test_google_news_request_is_restricted_to_country_and_language():
    responses.add(responses.GET, google_news.BASE, body=RSS, status=200)
    google_news.collect()
    url = responses.calls[0].request.url
    assert "hl=pt-BR" in url and "gl=BR" in url and "ceid=BR%3Apt" in url or "ceid=BR:pt" in url
