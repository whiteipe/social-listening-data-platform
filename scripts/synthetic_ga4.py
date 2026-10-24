"""Export GA4 -> BigQuery SINTÉTICO, no formato bruto aninhado (`events_YYYYMMDD`).

Schema conforme a documentação vigente do GA4 (support.google.com/analytics/answer/7029846, 24/10/2026).
O export real NÃO tem coluna de "sintético". Aqui os dados se identificam por: hostname
`exemplo-sintetico.invalid`, `stream_id` 1000000001 e `user_pseudo_id` com prefixo `SYN`.

Dificuldades reproduzidas (todas por parâmetro):
  * `traffic_source` é o first touch do USUÁRIO, não da sessão: para usuário recorrente difere do
    meio da sessão atual. O meio da sessão vem de event_params (source/medium), de
    collected_traffic_source e de session_traffic_source_last_click.
  * não há linha de "sessão": sessão = (user_pseudo_id, ga_session_id) e nasce do evento session_start.
  * event_date no fuso da propriedade (Brasília); event_timestamp em microssegundos UTC.
  * consentimento negado: privacy_info.analytics_storage = 'No'; HIPÓTESE (a documentação não diz o que
    acontece): sem user_pseudo_id, sem ga_session_id e sem traffic_source, então não dá para sessionizar.
  * tabelas dos 3 últimos dias chegam incompletas (a documentação diz que são atualizadas por até 3 dias).
  * bots: sessões diretas em massa, sem first_visit, sem engajamento, país estranho.
Valores aninhados de event_params vêm como STRUCT (string_value/int_value/float_value/double_value).
"""
from __future__ import annotations

import gzip
import json
from collections.abc import Callable, Iterator
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import numpy as np

TZ_OFFSET = timedelta(hours=-3)  # America/Sao_Paulo (sem horário de verão desde 2019)
STREAM_ID = "1000000001"
HOSTNAME = "exemplo-sintetico.invalid"
SESSION_SCALE = 0.25  # fração das sessões "cheias": mantém o export com ~200 mil eventos em 150 dias
NEW_USER_SHARE = 0.30
LATE_ARRIVAL_MISSING = {1: 0.05, 2: 0.02, 3: 0.005}  # dias atrás -> fração de eventos ainda ausente
FIRST_TOUCH_MIX = {"organic": 0.55, "(none)": 0.30, "cpc": 0.15}  # first touch de usuário recorrente
MEDIA = {"(none)": ("(direct)", "(none)"), "organic": ("google", "organic"), "cpc": ("google", "cpc")}
DEVICES = [("mobile", 0.70), ("desktop", 0.28), ("tablet", 0.02)]
OSES = {"mobile": [("Android", 0.72), ("iOS", 0.28)], "desktop": [("Windows", 0.8), ("Macintosh", 0.2)],
        "tablet": [("Android", 0.5), ("iOS", 0.5)]}
BROWSERS = [("Chrome", 0.68), ("Safari", 0.2), ("Samsung Internet", 0.07), ("Edge", 0.05)]
REGIONS = [("Sao Paulo", "Sao Paulo", 0.35), ("Rio de Janeiro", "Rio de Janeiro", 0.15),
           ("Minas Gerais", "Belo Horizonte", 0.12), ("Bahia", "Salvador", 0.08), ("Parana", "Curitiba", 0.07),
           ("Rio Grande do Sul", "Porto Alegre", 0.07), ("Ceara", "Fortaleza", 0.06), ("Pernambuco", "Recife", 0.05),
           ("Distrito Federal", "Brasilia", 0.05)]
PAGES = [("/", "Planos de internet e celular"), ("/fibra", "Internet fibra"), ("/planos/controle", "Planos controle"),
         ("/atendimento", "Atendimento"), ("/fatura", "Segunda via da fatura")]
HOUR_WEIGHTS = np.array([1, 1, 1, 1, 1, 2, 3, 4, 5, 6, 6, 7, 8, 7, 6, 6, 6, 7, 8, 9, 10, 9, 5, 2], dtype=float)


# --- schema BigQuery (colunas e tipos conforme a documentação) ----------------------------------------
def _f(name: str, type_: str = "STRING", mode: str = "NULLABLE", fields: list | None = None) -> dict:
    out = {"name": name, "type": type_, "mode": mode}
    if fields:
        out["fields"] = fields
    return out


def _strings(*names: str) -> list[dict]:
    return [_f(n) for n in names]


def _param_value(extra: list | None = None) -> dict:
    return _f("value", "RECORD", fields=[_f("string_value"), _f("int_value", "INTEGER"),
                                         _f("float_value", "FLOAT"), _f("double_value", "FLOAT"), *(extra or [])])


def ga4_schema() -> list[dict]:
    cs = _strings("campaign_name", "campaign_id", "source", "medium")
    return [
        _f("event_date"), _f("event_timestamp", "INTEGER"), _f("event_name"),
        _f("event_params", "RECORD", "REPEATED", [_f("key"), _param_value()]),
        _f("event_previous_timestamp", "INTEGER"), _f("event_value_in_usd", "FLOAT"),
        _f("event_bundle_sequence_id", "INTEGER"), _f("event_server_timestamp_offset", "INTEGER"),
        _f("user_id"), _f("user_pseudo_id"),
        _f("privacy_info", "RECORD", fields=_strings("analytics_storage", "ads_storage", "uses_transient_token")),
        _f("user_properties", "RECORD", "REPEATED",
           [_f("key"), _param_value([_f("set_timestamp_micros", "INTEGER")])]),
        _f("user_first_touch_timestamp", "INTEGER"),
        _f("user_ltv", "RECORD", fields=[_f("revenue", "FLOAT"), _f("currency")]),
        _f("device", "RECORD", fields=[
            *_strings("category", "mobile_brand_name", "mobile_model_name", "mobile_marketing_name",
                      "mobile_os_hardware_model", "operating_system", "operating_system_version", "vendor_id",
                      "advertising_id", "language"),
            _f("is_limited_ad_tracking"), _f("time_zone_offset_seconds", "INTEGER"),
            _f("web_info", "RECORD", fields=_strings("browser", "browser_version", "hostname"))]),
        _f("geo", "RECORD", fields=_strings("continent", "sub_continent", "country", "region", "metro", "city")),
        _f("app_info", "RECORD", fields=_strings("id", "firebase_app_id", "version", "install_source")),
        _f("traffic_source", "RECORD", fields=_strings("name", "medium", "source")),
        _f("stream_id"), _f("platform"),
        _f("event_dimensions", "RECORD", fields=[_f("hostname")]),
        _f("ecommerce", "RECORD", fields=[
            _f("total_item_quantity", "INTEGER"), _f("purchase_revenue_in_usd", "FLOAT"),
            _f("purchase_revenue", "FLOAT"), _f("unique_items", "INTEGER"), _f("transaction_id")]),
        _f("items", "RECORD", "REPEATED", [_f("item_id"), _f("item_name"), _f("quantity", "INTEGER"),
                                           _f("price", "FLOAT")]),
        _f("collected_traffic_source", "RECORD", fields=_strings(
            "manual_campaign_id", "manual_campaign_name", "manual_source", "manual_medium", "manual_term",
            "manual_content", "manual_creative_format", "manual_marketing_tactic", "manual_source_platform",
            "gclid", "dclid", "srsltid")),
        _f("is_active_user", "BOOLEAN"),
        _f("batch_event_index", "INTEGER"), _f("batch_page_id", "INTEGER"), _f("batch_ordering_id", "INTEGER"),
        _f("session_traffic_source_last_click", "RECORD", fields=[
            _f("manual_campaign", "RECORD", fields=_strings(
                "campaign_id", "campaign_name", "medium", "term", "content", "source_platform", "source",
                "creative_format", "marketing_tactic")),
            _f("google_ads_campaign", "RECORD", fields=_strings(
                "customer_id", "account_name", "campaign_id", "campaign_name", "ad_group_id", "ad_group_name")),
            _f("cross_channel_campaign", "RECORD", fields=_strings(
                "campaign_name", "campaign_id", "source_platform", "source", "medium")),
            _f("sa360_campaign", "RECORD", fields=cs), _f("dv360_campaign", "RECORD", fields=cs),
            _f("cm360_campaign", "RECORD", fields=cs)]),
    ]


# --- geração ---------------------------------------------------------------------------------------------
def _choice(rng, options):
    labels = [o[0] for o in options]
    p = np.array([o[-1] for o in options], dtype=float)
    return options[int(rng.choice(len(labels), p=p / p.sum()))]


def _param(key: str, *, s: str | None = None, i: int | None = None) -> dict:
    value = {"string_value": s} if s is not None else {"int_value": i}
    return {"key": key, "value": value}


def _micros(local: datetime) -> int:
    return int((local - TZ_OFFSET).replace(tzinfo=UTC).timestamp() * 1_000_000)


def _session_events(rng, d: date, medium: str, *, bot: bool, denied: bool, seq: list[int]) -> list[dict]:
    hour = int(rng.choice(24, p=HOUR_WEIGHTS / HOUR_WEIGHTS.sum()))
    local = datetime(d.year, d.month, d.day, hour, int(rng.integers(0, 60)), int(rng.integers(0, 60)))
    ts0 = _micros(local)
    src, med = MEDIA[medium]
    device_cat = "desktop" if bot else _choice(rng, DEVICES)[0]
    os_name = "Windows" if bot else _choice(rng, OSES[device_cat])[0]
    browser = "Chrome" if bot else _choice(rng, BROWSERS)[0]
    region, city, _ = (("California", "Mountain View", 1.0) if bot else _choice(rng, REGIONS))
    new_user = (not bot) and (not denied) and rng.random() < NEW_USER_SHARE
    ga_session_id = int(ts0 // 1_000_000)
    # id estilo GA4 (<aleatório>.<epoch do 1º acesso>), com prefixo SYN para identificar o sintético
    first_visit_s = ga_session_id if new_user else ga_session_id - int(rng.integers(86_400, 86_400 * 90))
    pseudo = None if denied else f"SYN{int(rng.integers(10**8, 10**9))}.{first_visit_s}"
    # first touch do USUÁRIO: igual à sessão se o usuário é novo; senão, sorteado (pode diferir da sessão atual)
    ft_medium = medium if new_user or bot else _choice(rng, list(FIRST_TOUCH_MIX.items()))[0]
    ft_src, ft_med = MEDIA[ft_medium]
    first_touch_ts = None if denied else (ts0 if new_user else ts0 - int(rng.integers(1, 90)) * 86_400_000_000)

    base = {
        "event_date": d.strftime("%Y%m%d"), "user_pseudo_id": pseudo, "stream_id": STREAM_ID, "platform": "WEB",
        "privacy_info": {"analytics_storage": "No" if denied else ("Unset" if bot else "Yes"),
                         "ads_storage": "No" if denied else "Unset", "uses_transient_token": "No"},
        "device": {"category": device_cat, "operating_system": os_name, "language": "pt-br",
                   "time_zone_offset_seconds": int(TZ_OFFSET.total_seconds()),
                   "web_info": {"browser": browser, "browser_version": "130.0", "hostname": HOSTNAME}},
        "geo": {"continent": "Americas", "sub_continent": "South America" if not bot else "Northern America",
                "country": "United States" if bot else "Brazil", "region": region, "city": city},
        "user_first_touch_timestamp": first_touch_ts,
    }
    if not denied:
        base["traffic_source"] = {"name": "(direct)" if ft_medium == "(none)" else "(organic)" if ft_medium == "organic"
                                  else "sintetica_campanha", "medium": ft_med, "source": ft_src}
        sess_param = [_param("ga_session_id", i=ga_session_id),
                      _param("ga_session_number", i=1 if new_user else int(rng.integers(2, 12)))]
        base["session_traffic_source_last_click"] = (
            {"manual_campaign": {"campaign_name": "sintetica_campanha", "source": src, "medium": med}}
            if medium == "cpc" else
            {"cross_channel_campaign": {"campaign_name": "(organic)" if medium == "organic" else "(direct)",
                                        "source": src, "medium": med}})
    else:
        sess_param = []
    page, title = PAGES[int(rng.integers(0, len(PAGES)))]
    referrer = {"organic": "https://www.google.com/", "cpc": "https://www.google.com/", "(none)": ""}[medium]
    n_pv = 1 if bot else 1 + int(rng.poisson(0.6))
    names = (["first_visit"] if new_user else []) + ["session_start"] + ["page_view"] * n_pv
    rows, t = [], ts0
    for k, name in enumerate(names):
        seq[0] += 1
        params = [*sess_param, _param("page_location", s=f"https://{HOSTNAME}{page}"), _param("page_title", s=title)]
        first_page = name == "page_view" and sum(1 for n in names[: k + 1] if n == "page_view") == 1
        if name in ("session_start", "first_visit") or first_page:
            params += [_param("source", s=src), _param("medium", s=med),
                       _param("campaign", s="sintetica_campanha" if medium == "cpc" else "(direct)" if medium == "(none)" else "(organic)")]
        if first_page:
            params += [_param("page_referrer", s=referrer), _param("entrances", i=1)]
        engagement = 0 if bot else int(rng.exponential(25_000)) if name == "page_view" else 0
        if name == "page_view":
            params.append(_param("engagement_time_msec", i=engagement))
            params.append(_param("session_engaged", s="1" if engagement > 10_000 else "0"))
        row = dict(base, event_timestamp=t, event_name=name, event_params=params, event_bundle_sequence_id=seq[0],
                   event_server_timestamp_offset=int(rng.integers(50_000, 900_000)),
                   is_active_user=bool(engagement > 0))
        if medium == "cpc" and not denied and (name == "session_start" or first_page):
            row["collected_traffic_source"] = {"manual_source": "google", "manual_medium": "cpc",
                                               "manual_campaign_name": "sintetica_campanha",
                                               "gclid": f"SYN{int(rng.integers(10**9, 10**10))}"}
        rows.append(row)
        t += int(rng.integers(1, 40)) * 1_000_000 if name == "page_view" else 1_000
    return rows


def iter_ga4_days(days: list[date], demand: np.ndarray, as_of: date, seed: int,
                  calendar_factor: Callable[[date], float], campaign_factor: Callable[[date], float],
                  bot_days: dict[date, float], denied_share: float) -> Iterator[tuple[date, list[dict]]]:
    """Gera um dia por vez (streaming): o export completo não cabe em memória como lista."""
    rng = np.random.default_rng(seed + 1000)
    seq = [0]
    for i, d in enumerate(days):
        if d >= as_of:  # o export diário do dia corrente só existe no dia seguinte
            continue
        cal = calendar_factor(d)
        bot_x = bot_days.get(d, 1.0)
        counts = {"(none)": (300.0 * cal * np.exp(rng.normal(0, 0.08)) + 0.15 * demand[i]) * SESSION_SCALE,
                  "organic": (0.55 * demand[i] + 500 * cal) * SESSION_SCALE,
                  "cpc": 250.0 * cal * campaign_factor(d) * SESSION_SCALE}
        rows: list[dict] = []
        for medium, mean in counts.items():
            n = int(rng.poisson(mean))
            n_bot = int(n * (1 - 1 / bot_x)) if medium == "(none)" and bot_x > 1 else 0
            for k in range(n):
                rows += _session_events(rng, d, medium, bot=k < n_bot, denied=rng.random() < denied_share, seq=seq)
        age = (as_of - d).days
        if age in LATE_ARRIVAL_MISSING:  # ainda chegando: parte dos eventos ausente neste momento
            keep = rng.random(len(rows)) >= LATE_ARRIVAL_MISSING[age]
            rows = [r for r, k in zip(rows, keep, strict=True) if k]
        yield d, rows


def write_shards(days_iter: Iterator[tuple[date, list[dict]]], out_dir: Path) -> dict:
    """Um arquivo `events_YYYYMMDD.jsonl.gz` por dia (como as tabelas fragmentadas do export) + schema.json."""
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "schema.json").write_text(json.dumps(ga4_schema(), indent=1), encoding="utf-8")
    shards = events = 0
    for d, rows in days_iter:
        with gzip.open(out_dir / f"events_{d:%Y%m%d}.jsonl.gz", "wt", encoding="utf-8") as fh:
            fh.write("\n".join(json.dumps(r, ensure_ascii=False) for r in rows))
        shards += 1
        events += len(rows)
    return {"shards": shards, "events": events}
