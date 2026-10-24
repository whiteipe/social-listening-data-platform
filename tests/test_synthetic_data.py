"""O gerador sintético precisa casar com o schema raw e reproduzir as dificuldades acordadas."""
from datetime import UTC, date, datetime

import numpy as np
import pandas as pd
import pytest

from scripts import synthetic_data as sd
from scripts.synthetic_ga4 import ga4_schema
from src.common.bq import SCHEMAS

AS_OF = date(2026, 10, 24)


@pytest.fixture(scope="module")
def realistic():
    return sd.generate("realistic", AS_OF, seed=42)


@pytest.fixture(scope="module")
def lag3():
    return sd.generate("lag3", AS_OF, seed=42)


def _daily(rows, key, value, date_col="date"):
    df = pd.DataFrame(rows)
    return df.groupby(date_col)[value].sum() if value else df.groupby(date_col).size()


@pytest.mark.parametrize("table, schema", [("mentions", "mentions"), ("mention_labels", "mention_labels"),
                                           ("trends_daily", "trends_daily"), ("social_daily", "social_daily")])
def test_rows_match_raw_schema(realistic, table, schema):
    cols = {f.name for f in SCHEMAS[schema]}
    required = {f.name for f in SCHEMAS[schema] if f.mode == "REQUIRED"}
    rows = getattr(realistic, table)
    assert rows
    for r in rows[:500]:
        assert set(r) == cols
        assert all(r[c] is not None for c in required)


def test_mentions_dates_are_utc_dates_of_published_at(realistic):
    for r in realistic.mentions[:300]:
        if r["date"] == datetime.fromisoformat(r["published_at"]).date().isoformat():
            continue
        # único desvio permitido: reaparição com data deslocada (exercita o dedupe)
        assert (date.fromisoformat(r["date"]) - datetime.fromisoformat(r["published_at"]).date()).days == 1


def test_everything_is_flagged_synthetic(realistic):
    assert all("synthetic" in r["mention_id"] and r["url"].startswith("https://synthetic.invalid")
               for r in realistic.mentions)
    assert all(r["is_synthetic"] for r in realistic.gsc)
    assert all(r["model_version"] == "synthetic-generator" for r in realistic.mention_labels)


def test_no_real_identifier_like_values(realistic):
    assert all(r["author_hash"].startswith("synthetic") for r in realistic.mentions)


def test_deterministic_for_same_seed_and_as_of():
    a, b = sd.generate("realistic", AS_OF, seed=7), sd.generate("realistic", AS_OF, seed=7)
    assert a.mentions == b.mentions and a.gsc == b.gsc
    first = lambda x: [next(iter(x.iter_ga4()))[1][:50]]  # noqa: E731 — GA4 é streaming: compara o 1º dia
    assert first(a) == first(b)
    assert sd.generate("realistic", AS_OF, seed=8).mentions != a.mentions


def test_gsc_lag_preliminary_and_anonymous(realistic):
    gsc = pd.DataFrame(realistic.gsc)
    assert gsc["data_date"].max() == (AS_OF - pd.Timedelta(days=sd.GSC_LAG_DAYS)).isoformat()
    assert set(gsc.loc[gsc["data_state"] == "preliminary", "data_date"]) == {
        (AS_OF - pd.Timedelta(days=d)).isoformat() for d in range(sd.GSC_LAG_DAYS, sd.GSC_LAG_DAYS + sd.GSC_PRELIM_DAYS)}
    anon = gsc[gsc["is_anonymized_query"]]
    assert anon["query"].isna().all()
    share = anon["clicks"].sum() / gsc["clicks"].sum()
    assert 0.10 < share < 0.30  # parte dos cliques sem texto de query


def test_gsc_has_regex_noise_queries(realistic):
    queries = {r["query"] for r in realistic.gsc if r["query"]}
    assert "tv ao vivo" in queries and "vivo fibra" in queries  # "ao vivo" casa com o regex ingênuo da marca


def test_trends_is_relative_zero_to_100_without_partial_day(realistic):
    t = pd.DataFrame(realistic.trends_daily)
    assert t["interest"].between(0, 100).all() and t["interest"].max() == 100
    assert t["date"].max() < AS_OF.isoformat()


def test_crisis_window_raises_brand_negatives(realistic):
    labels = pd.DataFrame(realistic.mention_labels)
    m = pd.DataFrame(realistic.mentions)[["source", "mention_id", "query_group"]].drop_duplicates()
    df = labels.merge(m, on=["source", "mention_id"])
    df = df[df["query_group"] == "marca"]
    neg = df[df["sentiment"] == "negative"].groupby("date").size()
    crisis = neg.reindex(["2026-09-30", "2026-10-01", "2026-10-02"]).mean()
    assert crisis > 3 * neg.drop(["2026-09-30", "2026-10-01", "2026-10-02"], errors="ignore").median()


def _lag_corr(data, lags=range(0, 15), detrend=False):
    brand = pd.DataFrame(data.mentions)
    brand = brand[brand["query_group"] == "marca"].drop_duplicates(["source", "mention_id"])
    mentions = brand.groupby("date").size()
    gsc = pd.DataFrame(data.gsc)
    clicks = gsc[gsc["query"].notna() & gsc["query"].str.startswith("vivo")].groupby("data_date")["clicks"].sum()
    idx = pd.date_range(AS_OF - pd.Timedelta(days=sd.WINDOW_DAYS - 1), AS_OF - pd.Timedelta(days=3))
    m = np.array(mentions.reindex(idx.strftime("%Y-%m-%d")).fillna(0), dtype=float)
    c = np.array(clicks.reindex(idx.strftime("%Y-%m-%d")).fillna(0), dtype=float)
    if detrend:  # remove o efeito do dia da semana
        dow = idx.day_of_week.to_numpy()
        for arr in (m, c):
            for d in range(7):
                arr[dow == d] -= arr[dow == d].mean()
    return {k: float(np.corrcoef(m[: len(m) - k], c[k:])[0, 1]) for k in lags}


def test_lag3_scenario_recovers_injected_lag(lag3):
    corr = _lag_corr(lag3, detrend=True)
    assert max(corr, key=corr.get) == sd.INJECTED_LAG_DAYS
    assert corr[sd.INJECTED_LAG_DAYS] > 0.5


def test_realistic_scenario_has_no_signal_at_the_injected_lag(realistic):
    corr = _lag_corr(realistic, detrend=True)
    assert abs(corr[sd.INJECTED_LAG_DAYS]) < 0.25  # sem lag causal embutido
    assert max(corr, key=lambda k: abs(corr[k])) != sd.INJECTED_LAG_DAYS


def test_realistic_scenario_shows_confounded_correlation_at_short_lags():
    """A armadilha que o cenário existe para mostrar: campanhas e feriados movem menções e buscas
    juntos, então há correlação em lag 0 sem causa. Vale na média de várias sementes."""
    lag0 = [_lag_corr(sd.generate("realistic", AS_OF, seed=s), lags=[0], detrend=True)[0] for s in range(8)]
    assert np.mean(lag0) > 0.15


def test_noise_alone_produces_sizable_max_correlation_across_15_lags(realistic):
    """Comparações múltiplas: com ~100 dias e 15 lags, o maior |corr| de ruído já passa de 0,2."""
    vals = [max(abs(v) for v in _lag_corr(sd.generate("realistic", AS_OF, seed=s), detrend=True).values())
            for s in range(8)]
    assert np.mean(vals) > 0.2


# ---------------------------------------------------------------- export GA4 bruto (events_YYYYMMDD)
@pytest.fixture(scope="module")
def ga4_days(realistic):
    return dict(realistic.iter_ga4())


def _check_keys(row, fields, path=""):
    known = {f["name"]: f for f in fields}
    for k, v in row.items():
        assert k in known, f"coluna fora do schema: {path}{k}"
        sub = known[k].get("fields")
        if sub and isinstance(v, dict):
            _check_keys(v, sub, f"{path}{k}.")
        elif sub and isinstance(v, list):
            for item in v:
                _check_keys(item, sub, f"{path}{k}[].")


def _events(ga4_days, n=12):
    return [r for d in list(ga4_days)[:n] for r in ga4_days[d]]


def _param(row, key):
    return next((p["value"] for p in row["event_params"] if p["key"] == key), None)


def test_window_is_150_days_and_no_collection_gaps(realistic, ga4_days):
    days = {r["date"] for r in realistic.mentions}
    assert sd.WINDOW_DAYS == 150
    expected = {(AS_OF - pd.Timedelta(days=i)).strftime("%Y-%m-%d") for i in range(sd.WINDOW_DAYS)}
    assert len(expected - days) <= 1  # o primeiro dia pode perder só a ponta por causa do fuso
    assert len(ga4_days) == sd.WINDOW_DAYS - 1  # um shard por dia; o dia corrente só sai no dia seguinte
    assert AS_OF not in ga4_days


def test_ga4_rows_follow_the_documented_export_schema(ga4_days):
    schema = ga4_schema()
    top = {f["name"] for f in schema}
    assert {"event_date", "event_timestamp", "event_name", "event_params", "user_pseudo_id", "privacy_info",
            "traffic_source", "collected_traffic_source", "session_traffic_source_last_click", "device",
            "geo"} <= top
    for d in list(ga4_days)[:3]:
        for row in ga4_days[d][:200]:
            _check_keys(row, schema)
            assert row["event_date"] == d.strftime("%Y%m%d")
            for p in row["event_params"]:
                assert set(p["value"]) <= {"string_value", "int_value", "float_value", "double_value"}


def test_ga4_is_identifiable_as_synthetic_without_a_flag_column(ga4_days):
    rows = next(iter(ga4_days.values()))
    assert all(r["device"]["web_info"]["hostname"] == "exemplo-sintetico.invalid" for r in rows)
    assert all(r["user_pseudo_id"] is None or r["user_pseudo_id"].startswith("SYN") for r in rows)


def test_traffic_source_is_first_touch_and_differs_from_session_medium(ga4_days):
    """A armadilha do README original: traffic_source.medium NÃO é o meio da sessão."""
    rows = [r for r in _events(ga4_days) if r["event_name"] == "session_start" and "traffic_source" in r]
    differs = sum(1 for r in rows if r["traffic_source"]["medium"] != _param(r, "medium")["string_value"])
    assert 0.15 < differs / len(rows) < 0.70  # usuários recorrentes chegam por outro meio


def test_sessions_come_from_session_start_and_first_visit_marks_new_users(ga4_days):
    rows = _events(ga4_days)
    starts = [r for r in rows if r["event_name"] == "session_start" and r["user_pseudo_id"]]
    ids = [(r["user_pseudo_id"], _param(r, "ga_session_id")["int_value"]) for r in starts]
    assert len(ids) == len(set(ids))  # uma sessão = um session_start por (usuário, ga_session_id)
    new_share = sum(1 for r in rows if r["event_name"] == "first_visit") / len(starts)
    assert 0.2 < new_share < 0.4
    assert any(r["event_name"] == "page_view" for r in rows)


def test_denied_consent_cannot_be_sessionized(ga4_days):
    """Hipótese (a documentação não detalha): sem consentimento, sem user_pseudo_id e sem ga_session_id."""
    rows = _events(ga4_days)
    denied = [r for r in rows if r["privacy_info"]["analytics_storage"] == "No"]
    assert 0.12 < len(denied) / len(rows) < 0.32
    assert all(r["user_pseudo_id"] is None and "traffic_source" not in r for r in denied)
    assert all(_param(r, "ga_session_id") is None for r in denied)


def test_ga4_timestamps_are_utc_micros_and_event_date_is_brasilia(ga4_days):
    for d, rows in list(ga4_days.items())[:3]:
        for r in rows[:300]:
            local = datetime.fromtimestamp(r["event_timestamp"] / 1_000_000, tz=UTC).replace(tzinfo=None) \
                - pd.Timedelta(hours=3)
            assert local.strftime("%Y%m%d") == r["event_date"] == d.strftime("%Y%m%d")


def test_ga4_bot_spike_is_foreign_direct_traffic_without_new_users(ga4_days):
    us = [r for r in ga4_days[date(2026, 8, 14)] if r["geo"]["country"] == "United States"]
    normal = [r for r in ga4_days[date(2026, 8, 13)] if r["geo"]["country"] == "United States"]
    assert len(us) > 5 * max(len(normal), 1)
    assert all(r["traffic_source"]["medium"] == "(none)" for r in us if "traffic_source" in r)
    assert not any(r["event_name"] == "first_visit" for r in us)


def test_most_recent_ga4_shards_are_incomplete_until_late_events_arrive(ga4_days):
    sizes = {d: len(rows) for d, rows in ga4_days.items()}
    older = np.median([sizes[AS_OF - pd.Timedelta(days=k).to_pytimedelta()] for k in range(8, 20)])
    assert sizes[AS_OF - pd.Timedelta(days=1).to_pytimedelta()] < older * 1.05
