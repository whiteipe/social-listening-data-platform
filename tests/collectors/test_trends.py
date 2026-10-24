from src.collectors import trends


def _result(points):
    return {"interest_over_time": points}


def _pt(date, vals, partial=False):
    return {"date": f"{date}T00:00:00+00:00", "values": vals, "is_partial": partial}


def _patch(monkeypatch, fn):
    monkeypatch.setattr(trends, "load_trends", lambda: (["a", "b"], "BR"))
    monkeypatch.setattr(trends.trendspyg, "download_google_trends_comparison", fn)


def test_trends_rows_and_partial_dropped(monkeypatch):
    calls = []

    def fake(terms, **kw):
        calls.append((terms, kw))
        return _result([_pt("2026-10-20", {"a": 10, "b": 1}), _pt("2026-10-21", {"a": 20, "b": 2}),
                        _pt("2026-10-22", {"a": 30, "b": 3}, partial=True)])

    _patch(monkeypatch, fake)
    rows = trends.collect()
    assert len(rows) == 4  # 2 dias fechados x 2 termos; o dia parcial é descartado
    assert {r["date"] for r in rows} == {"2026-10-20", "2026-10-21"}
    assert all(r["geo"] == "BR" and isinstance(r["interest"], int) for r in rows)
    assert len(calls) == 1 and calls[0][0] == ["a", "b"]  # mesma chamada: termos comparáveis
    assert calls[0][1]["geo"] == "BR"
    assert calls[0][1]["engine"] == "auto"  # direto primeiro, Chrome só como reserva


def test_trends_failure_does_not_break_pipeline(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("429 Too Many Requests")

    _patch(monkeypatch, boom)
    assert trends.collect() == []


def test_trends_empty_result(monkeypatch):
    _patch(monkeypatch, lambda *a, **k: _result([]))
    assert trends.collect() == []


def test_trends_missing_term_value_is_skipped(monkeypatch):
    _patch(monkeypatch, lambda *a, **k: _result([_pt("2026-10-20", {"a": 5})]))
    rows = trends.collect()
    assert [(r["term"], r["interest"]) for r in rows] == [("a", 5)]
