"""O gerador sintético precisa casar com o schema raw e reproduzir as dificuldades acordadas."""
from datetime import date, datetime

import numpy as np
import pandas as pd
import pytest

from scripts import synthetic_data as sd
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
    assert all(r["is_synthetic"] for r in realistic.gsc + realistic.ga4)
    assert all(r["model_version"] == "synthetic-generator" for r in realistic.mention_labels)


def test_no_real_identifier_like_values(realistic):
    assert all(r["author_hash"].startswith("synthetic") for r in realistic.mentions)


def test_deterministic_for_same_seed_and_as_of():
    a, b = sd.generate("realistic", AS_OF, seed=7), sd.generate("realistic", AS_OF, seed=7)
    assert a.mentions == b.mentions and a.gsc == b.gsc and a.ga4 == b.ga4
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


def test_ga4_has_consent_gap_outage_and_bot_spike(realistic):
    ga4 = pd.DataFrame(realistic.ga4)
    assert (ga4["consent_state"] == "denied").any()
    days = set(ga4["event_date"])
    assert "20260828" not in days and "20260829" not in days  # falha da tag
    direct = ga4[(ga4["event_name"] == "session_start") & (ga4["traffic_medium"] == "(none)")]
    by_day = direct.groupby("event_date")["event_count"].sum()
    assert by_day["20260814"] > 3 * by_day.median()  # pico de bot em sessões diretas


def test_collection_gap_is_a_brasilia_day_not_a_utc_day(realistic):
    """A falha de coleta cobre o dia de Brasília (03:00Z a 03:00Z); em UTC, o dia 09-02 ainda tem
    as menções das 21h às 24h do dia anterior. Esse deslocamento de fuso é intencional."""
    ts = [datetime.fromisoformat(r["published_at"]) for r in realistic.mentions]
    start, end = datetime.fromisoformat("2026-09-02T03:00:00+00:00"), datetime.fromisoformat("2026-09-03T03:00:00+00:00")
    assert not any(start <= t < end for t in ts)
    assert any(t.date().isoformat() == "2026-09-02" and t < start for t in ts)  # sobra em UTC


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
