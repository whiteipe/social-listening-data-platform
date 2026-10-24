"""Gerador de dados SINTÉTICOS: menções, labels, Trends, GSC e GA4 para testar o pipeline.

Nada aqui é dado real. Tudo sai marcado como sintético (`is_synthetic`, ids `synthetic-...`,
`metrics.is_synthetic`, `model_version = synthetic-generator`, urls `synthetic.invalid`).

O objetivo é reproduzir as DIFICULDADES de cruzar fontes externas, não só o sinal:
  * fuso: menções em UTC, GA4 no fuso da propriedade (Brasília), GSC no fuso do Pacífico
    (parte dos cliques da madrugada de Brasília cai no dia anterior);
  * atraso e revisão: o GSC chega com 2 dias de atraso e os 3 últimos dias disponíveis são
    preliminares (valores menores, depois revisados);
  * queries anônimas: parte dos cliques do GSC vem sem texto de query;
  * consentimento no GA4: sessões com consentimento negado e novos usuários subcontados;
  * lacunas: falha de coleta de menções (1 dia) e de tag do GA4 (2 dias);
  * picos de bot: sessões diretas multiplicadas sem novos usuários;
  * sazonalidade semanal e feriados;
  * confundidores: campanhas empurram menções E buscas ao mesmo tempo (correlação sem causa);
  * ruído de regex: queries "ao vivo" que casam com o nome da marca;
  * Trends relativo (0 a 100, renormalizado pelo termo mais forte), com zeros em dias fracos.

Dois cenários:
  realistic  menções e buscas compartilham só sazonalidade, feriados e campanhas; sem acoplamento
             direto. O que aparecer de correlação é, em boa parte, calendário e confundidor.
  lag3       cliques de marca = função das menções de 3 dias antes (+ ruído): serve para provar
             que mart_lag_correlation recupera um lag conhecido. NÃO é um achado de negócio.
"""
from __future__ import annotations

import argparse
import json
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import numpy as np

SEED_PARAMS_VERSION = "1.1"
DEFAULT_AS_OF = date(2026, 10, 24)  # fixo: mesmo seed + as_of = mesmos dados (os eventos abaixo são de 2026)
WINDOW_DAYS = 120
INJECTED_LAG_DAYS = 3
GROUPS = {"marca": 1.0, "concorrente_a": 0.62, "concorrente_b": 0.50}
GROUP_LABEL = {"marca": "Vivo", "concorrente_a": "Claro", "concorrente_b": "TIM"}
TRENDS_TERMS = {"marca": "operadora vivo", "concorrente_a": "operadora claro",
                "concorrente_b": "operadora tim"}
BRT_OFFSET = timedelta(hours=3)  # UTC = Brasília + 3h

WEEKDAY = {0: 1.00, 1: 1.05, 2: 1.05, 3: 1.00, 4: 0.95, 5: 0.80, 6: 0.60}  # segunda = 0
HOLIDAYS = {date(2026, 9, 7), date(2026, 10, 12)}
HOLIDAY_FACTOR = 0.75
CRISIS = (date(2026, 9, 30), date(2026, 10, 2))   # janela de crise da marca (Brasília)
CRISIS_VOLUME_X = 2.5
COLLECTION_GAP = {date(2026, 9, 2)}               # coletor de menções falhou o dia todo
GA4_OUTAGE = {date(2026, 8, 28), date(2026, 8, 29)}
BOT_DAYS = {date(2026, 8, 14): 6.0, date(2026, 9, 19): 6.0}
GSC_LAG_DAYS = 2            # último dia disponível = as_of - 2
GSC_PRELIM_DAYS = 3         # os 3 últimos dias disponíveis são preliminares
GSC_PRELIM_FACTOR = 0.70
GSC_PT_SPILL = 0.12         # fração dos cliques da madrugada de Brasília que cai no dia anterior (PT)
GSC_ANON_SHARE = 0.25
GA4_DENIED_SHARE = 0.22
LABELED_SHARE = 0.88
LABELED_SHARE_RECENT = 0.40  # últimos 2 dias: fila de classificação
LAST_DAY_HOURS = 14          # o dia corrente (as_of) é parcial

BRAND_QUERY_WEIGHTS = {
    "vivo fibra": 0.28, "vivo": 0.22, "operadora vivo": 0.12, "vivo internet": 0.14,
    "telefone vivo": 0.08, "vivo 0800": 0.06, "vivo planos": 0.10,
}
NOISE_QUERIES = {  # casam com o regex ingênuo da marca; precisam ser excluídos ("ao vivo")
    "jogo ao vivo hoje": 140, "tv ao vivo": 110, "futebol ao vivo": 90,
}
OTHER_QUERIES = {  # nada a ver com a marca ou concorrentes
    "melhor plano de internet": 60, "claro net": 45, "tim live": 40, "como trocar de operadora": 35,
}

TOPICS = ["preco", "qualidade", "entrega", "atendimento", "produto_defeito",
          "campanha_publicidade", "institucional", "concorrencia", "outros"]
TOPIC_WEIGHTS = {
    "negative": {"atendimento": .32, "produto_defeito": .22, "preco": .18, "qualidade": .14,
                 "entrega": .06, "institucional": .04, "outros": .04},
    "positive": {"qualidade": .26, "campanha_publicidade": .20, "preco": .18, "atendimento": .16,
                 "institucional": .08, "outros": .06, "concorrencia": .06},
    "neutral": {"outros": .24, "institucional": .20, "preco": .16, "concorrencia": .16,
                "campanha_publicidade": .12, "qualidade": .06, "atendimento": .06},
}
TEMPLATES = {
    "negative": ["{m} caiu de novo, internet horrível", "péssimo atendimento da {m}, ninguém resolve",
                 "{m} cobrou errado na fatura, cansei", "sinal da {m} sumiu aqui no bairro"],
    "positive": ["{m} resolveu na hora, atendimento nota 10", "internet da {m} está voando",
                 "gostei do plano novo da {m}", "boa a campanha da {m}"],
    "neutral": ["alguém sabe se a {m} tem cobertura em Campinas?", "qual o melhor plano da {m}?",
                "notícia: {m} anuncia mudança de planos", "comparando {m} com as outras operadoras"],
}
SOURCE_MIX = [("youtube_comment", 0.55), ("youtube_video", 0.10), ("news", 0.35)]
HOUR_WEIGHTS = np.array([1, 1, 1, 1, 1, 2, 3, 4, 5, 6, 6, 7, 8, 7, 6, 6, 6, 7, 8, 9, 10, 9, 5, 2],
                        dtype=float)


@dataclass
class Campaign:
    campaign_id: str
    name: str
    start: date
    end: date
    boost: float  # aumento relativo de menções durante a campanha


@dataclass
class SyntheticData:
    scenario: str
    as_of: date
    mentions: list[dict] = field(default_factory=list)
    mention_labels: list[dict] = field(default_factory=list)
    trends_daily: list[dict] = field(default_factory=list)
    social_daily: list[dict] = field(default_factory=list)
    gsc: list[dict] = field(default_factory=list)
    ga4: list[dict] = field(default_factory=list)


BOOSTS = {"awareness": 0.45, "consideracao": 0.30, "engajamento": 0.20}
CAMPAIGNS = [  # campanhas sintéticas; o dbt pode carregar este mesmo calendário como seed
    Campaign("c001", "[SINTETICA] Lancamento Fibra Giga", date(2026, 8, 3), date(2026, 8, 23),
             BOOSTS["awareness"]),
    Campaign("c002", "[SINTETICA] Parceria com creators", date(2026, 9, 14), date(2026, 9, 27),
             BOOSTS["consideracao"]),
    Campaign("c003", "[SINTETICA] Conteudo Dia do Cliente", date(2026, 10, 5), date(2026, 10, 11),
             BOOSTS["engajamento"]),
]
CAMPAIGN_META = {"c001": ("midia_paga", "awareness"), "c002": ("influenciadores", "consideracao"),
                 "c003": ("conteudo_organico", "engajamento")}


def _ar1(rng: np.random.Generator, n: int, phi: float, sigma: float) -> np.ndarray:
    e = np.zeros(n)
    for i in range(1, n):
        e[i] = phi * e[i - 1] + rng.normal(0, sigma)
    return e


def _calendar_factor(d: date) -> float:
    return WEEKDAY[d.weekday()] * (HOLIDAY_FACTOR if d in HOLIDAYS else 1.0)


def _campaign_factor(d: date, campaigns: list[Campaign], shift_days: int = 0) -> float:
    f = 1.0
    for c in campaigns:
        if c.start + timedelta(days=shift_days) <= d <= c.end + timedelta(days=shift_days):
            f *= 1.0 + c.boost
    return f


def _loaded_at(d: date) -> str:
    return datetime(d.year, d.month, d.day, 9, 0, tzinfo=UTC).isoformat()


def generate(scenario: str = "realistic", as_of: date | None = None, seed: int = 42,
             campaigns: list[Campaign] | None = None) -> SyntheticData:
    if scenario not in ("realistic", "lag3"):
        raise ValueError("scenario deve ser 'realistic' ou 'lag3'")
    as_of = as_of or DEFAULT_AS_OF
    rng = np.random.default_rng(seed)
    campaigns = campaigns if campaigns is not None else CAMPAIGNS
    days = [as_of - timedelta(days=WINDOW_DAYS - 1 - i) for i in range(WINDOW_DAYS)]
    n = len(days)
    out = SyntheticData(scenario=scenario, as_of=as_of)

    # --- intensidade diária de menções por grupo (Brasília) -----------------------------
    base = {"marca": 14.0, "concorrente_a": 9.0, "concorrente_b": 7.5}
    lam: dict[str, np.ndarray] = {}
    for g in GROUPS:
        noise = np.exp(_ar1(rng, n, 0.6, 0.22))
        lam[g] = np.array([
            base[g] * _calendar_factor(d) * _campaign_factor(d, campaigns if g == "marca" else [])
            * (CRISIS_VOLUME_X if g == "marca" and CRISIS[0] <= d <= CRISIS[1] else 1.0)
            for d in days]) * noise
    counts = {g: rng.poisson(lam[g]) for g in GROUPS}
    for i, d in enumerate(days):
        if d in COLLECTION_GAP:
            for g in GROUPS:
                counts[g][i] = 0
        if d == as_of:  # dia corrente parcial
            for g in GROUPS:
                counts[g][i] = int(counts[g][i] * LAST_DAY_HOURS / 24)

    # --- menções e labels -----------------------------------------------------------------
    _gen_mentions(out, rng, days, counts, campaigns)

    # --- demanda de busca de marca (S) ----------------------------------------------------
    m_series = counts["marca"].astype(float)
    if scenario == "lag3":
        valid = np.array([d not in COLLECTION_GAP for d in days])
        mu, sd = m_series[valid].mean(), m_series[valid].std()
        z = np.where(valid, (m_series - mu) / sd, 0.0)
        z_lag = np.concatenate([np.zeros(INJECTED_LAG_DAYS), z[:-INJECTED_LAG_DAYS]])
        demand = 900.0 * np.clip(1.0 + 0.8 * z_lag, 0.15, None) * np.exp(rng.normal(0, 0.05, n))
    else:
        s_noise = np.exp(_ar1(rng, n, 0.55, 0.20))
        demand = np.array([900.0 * _calendar_factor(d) * _campaign_factor(d, campaigns, shift_days=1)
                           for d in days]) * s_noise

    _gen_trends(out, rng, days, demand, lam, scenario)
    _gen_gsc(out, rng, days, demand, as_of)
    _gen_ga4(out, rng, days, demand, as_of, campaigns)
    _gen_social_daily(out, rng, days)
    return out


def _pick(rng: np.random.Generator, weights: dict[str, float]) -> str:
    keys = list(weights)
    p = np.array([weights[k] for k in keys], dtype=float)
    return keys[rng.choice(len(keys), p=p / p.sum())]


def _gen_mentions(out: SyntheticData, rng, days, counts, campaigns) -> None:
    seq = 0
    hours_p = HOUR_WEIGHTS / HOUR_WEIGHTS.sum()
    sources = [s for s, _ in SOURCE_MIX]
    src_p = np.array([p for _, p in SOURCE_MIX])
    for i, d in enumerate(days):
        recent = (out.as_of - d).days <= 1
        in_crisis = CRISIS[0] <= d <= CRISIS[1]
        in_campaign = _campaign_factor(d, campaigns) > 1.0
        for g in GROUPS:
            for _ in range(int(counts[g][i])):
                seq += 1
                src = sources[rng.choice(len(sources), p=src_p)]
                hour = int(rng.choice(24, p=hours_p))
                if d == out.as_of:
                    hour = min(hour, LAST_DAY_HOURS - 1)
                brt = datetime(d.year, d.month, d.day, hour, int(rng.integers(0, 60)), tzinfo=UTC)
                published = brt + BRT_OFFSET  # horário de Brasília -> UTC
                if g == "marca":
                    p_neg = 0.70 if in_crisis else 0.26
                    p_pos = 0.38 if in_campaign and not in_crisis else 0.30
                else:
                    p_neg, p_pos = 0.28, 0.28
                p_pos = min(p_pos, 1 - p_neg - 0.05)
                sentiment = ["negative", "positive", "neutral"][
                    rng.choice(3, p=[p_neg, p_pos, 1 - p_neg - p_pos])]
                weights = dict(TOPIC_WEIGHTS[sentiment])
                if in_crisis and g == "marca" and sentiment == "negative":
                    weights["atendimento"], weights["produto_defeito"] = 0.45, 0.35
                topic = _pick(rng, weights)
                item = f"synthetic-{src}-{seq:06d}"
                text = TEMPLATES[sentiment][int(rng.integers(0, len(TEMPLATES[sentiment])))].format(
                    m=GROUP_LABEL[g])
                engagement = None if src == "news" else int(rng.lognormal(0.8, 1.1))
                row = {
                    "source": src, "mention_id": f"{item}|{g}", "published_at": published.isoformat(),
                    "date": published.date().isoformat(), "text": text,
                    "author_hash": f"synthetic{int(rng.integers(0, 10**6)):06d}",
                    "url": f"https://synthetic.invalid/{item}", "query_group": g, "language": "pt",
                    "engagement": engagement, "reach": None,
                    "metrics": json.dumps({"is_synthetic": True}), "_loaded_at": _loaded_at(d),
                }
                out.mentions.append(row)
                labeled = rng.random() < (LABELED_SHARE_RECENT if recent else LABELED_SHARE)
                if labeled:
                    intent = {"negative": "reclamacao", "positive": "elogio"}.get(
                        sentiment, "duvida" if rng.random() < 0.4 else "neutro")
                    out.mention_labels.append({
                        "source": src, "mention_id": row["mention_id"], "date": row["date"],
                        "sentiment": sentiment, "sentiment_score": float(rng.uniform(0.55, 0.99)),
                        "topic": topic, "intent": intent, "model_version": "synthetic-generator",
                        "classified_at": _loaded_at(d + timedelta(days=1)),
                    })
                # item comparativo: mesma notícia/vídeo gravada também em outro grupo
                if src != "youtube_comment" and rng.random() < 0.04:
                    other = [x for x in GROUPS if x != g][int(rng.integers(0, 2))]
                    sib = dict(row, mention_id=f"{item}|{other}", query_group=other)
                    out.mentions.append(sib)
    # reaparições: mesmo mention_id com data UTC deslocada e carga posterior (exercita o dedupe)
    for row in out.mentions[::max(len(out.mentions) // 8, 1)][:8]:
        dup_date = (date.fromisoformat(row["date"]) + timedelta(days=1)).isoformat()
        out.mentions.append(dict(row, date=dup_date, _loaded_at=_loaded_at(date.fromisoformat(dup_date))))


def _gen_trends(out: SyntheticData, rng, days, demand, lam, scenario) -> None:
    n = len(days)
    raw = {}
    cal = np.array([_calendar_factor(d) for d in days])
    raw["marca"] = demand * np.exp(rng.normal(0, 0.10, n))
    for g, share in (("concorrente_a", 0.86), ("concorrente_b", 0.73)):
        raw[g] = 900.0 * share * cal * np.exp(_ar1(rng, n, 0.55, 0.18))
    peak = max(v.max() for v in raw.values())
    for g, series in raw.items():
        vals = np.rint(100 * series / peak).astype(int)
        for d, v in zip(days, vals, strict=True):
            if d >= out.as_of:  # o Trends não devolve o dia parcial
                continue
            out.trends_daily.append({"date": d.isoformat(), "term": TRENDS_TERMS[g], "geo": "BR",
                                     "interest": int(v), "_loaded_at": _loaded_at(d + timedelta(days=1))})


def _gen_gsc(out: SyntheticData, rng, days, demand, as_of) -> None:
    last_avail = as_of - timedelta(days=GSC_LAG_DAYS)
    prelim_from = last_avail - timedelta(days=GSC_PRELIM_DAYS - 1)
    acc: dict[tuple[date, str | None], list[float]] = {}

    def add(day: date, query: str | None, clicks: int, imps: int) -> None:
        spill = int(rng.binomial(clicks, GSC_PT_SPILL))
        for dd, c in ((day, clicks - spill), (day - timedelta(days=1), spill)):
            a = acc.setdefault((dd, query), [0, 0])
            a[0] += c
            a[1] += int(imps * (c / clicks)) if clicks else 0

    qs, qw = list(BRAND_QUERY_WEIGHTS), np.array(list(BRAND_QUERY_WEIGHTS.values()))
    for i, d in enumerate(days):
        total = demand[i]
        brand_total = total * (1 - GSC_ANON_SHARE)
        for q, w in zip(qs, qw, strict=True):
            c = int(rng.poisson(brand_total * w))
            if c:
                add(d, q, c, int(c * rng.uniform(12, 20)))
        anon = int(rng.poisson(total * GSC_ANON_SHARE))
        if anon:
            add(d, None, anon, int(anon * rng.uniform(10, 16)))
        for q, mean in {**NOISE_QUERIES, **OTHER_QUERIES}.items():
            c = int(rng.poisson(mean * _calendar_factor(d)))
            if c:
                add(d, q, c, int(c * rng.uniform(8, 25)))
    for (d, q), (clicks, imps) in sorted(acc.items(), key=lambda kv: (kv[0][0], kv[0][1] or "")):
        if d > last_avail or d < days[0]:
            continue  # ainda não disponível (atraso do GSC) ou fora da janela
        prelim = d >= prelim_from
        f = GSC_PRELIM_FACTOR if prelim else 1.0
        out.gsc.append({
            "data_date": d.isoformat(), "site_url": "sc-domain:exemplo-sintetico.invalid", "query": q,
            "is_anonymized_query": q is None, "country": "bra", "device": "MOBILE",
            "impressions": int(imps * f), "clicks": int(clicks * f),
            "data_state": "preliminary" if prelim else "final", "is_synthetic": True,
            "_loaded_at": _loaded_at(as_of),
        })


def _gen_ga4(out: SyntheticData, rng, days, demand, as_of, campaigns) -> None:
    for i, d in enumerate(days):
        if d in GA4_OUTAGE or d >= as_of:  # export do dia corrente só no dia seguinte
            continue
        cal = _calendar_factor(d)
        direct = (300.0 * cal * np.exp(rng.normal(0, 0.08)) + 0.15 * demand[i]) * BOT_DAYS.get(d, 1.0)
        organic = 0.55 * demand[i] + 500 * cal
        paid = 250.0 * cal * _campaign_factor(d, campaigns)
        sessions = {"(none)": direct, "organic": organic, "cpc": paid}
        for medium, val in sessions.items():
            val = val * rng.uniform(0.97, 1.03)  # amostragem/ruído de medição
            denied = int(val * GA4_DENIED_SHARE)
            for state, v in (("granted", int(val) - denied), ("denied", denied)):
                out.ga4.append({"event_date": d.strftime("%Y%m%d"), "event_name": "session_start",
                                "traffic_medium": medium, "consent_state": state, "event_count": v,
                                "is_synthetic": True, "_loaded_at": _loaded_at(d + timedelta(days=1))})
        bot = BOT_DAYS.get(d, 1.0) > 1
        new_users = int(0.30 * (organic + paid) + (0 if bot else 0.30 * direct)) * (1 - GA4_DENIED_SHARE)
        out.ga4.append({"event_date": d.strftime("%Y%m%d"), "event_name": "first_visit",
                        "traffic_medium": "(none)", "consent_state": "granted",
                        "event_count": int(new_users), "is_synthetic": True,
                        "_loaded_at": _loaded_at(d + timedelta(days=1))})


def _gen_social_daily(out: SyntheticData, rng, days) -> None:
    subs = 120_000.0
    for d in days:
        subs += rng.normal(40, 15)
        out.social_daily.append({"date": d.isoformat(), "platform": "youtube", "metric": "subscriberCount",
                                 "value": float(round(subs)), "_loaded_at": _loaded_at(d)})


TABLES = ("mentions", "mention_labels", "trends_daily", "social_daily", "gsc", "ga4")


def write(data: SyntheticData, out_dir: Path, seed: int) -> Path:
    """Grava um JSONL por tabela + campaign_calendar.csv + manifest.json. Só arquivos locais."""
    target = Path(out_dir) / data.scenario
    target.mkdir(parents=True, exist_ok=True)
    counts = {}
    for name in TABLES:
        rows = getattr(data, name)
        counts[name] = len(rows)
        (target / f"{name}.jsonl").write_text(
            "\n".join(json.dumps(r, ensure_ascii=False) for r in rows), encoding="utf-8")
    lines = ["campaign_id,name,channel,objective,start_date,end_date,is_synthetic"]
    for c in CAMPAIGNS:
        channel, objective = CAMPAIGN_META[c.campaign_id]
        lines.append(f"{c.campaign_id},{c.name},{channel},{objective},{c.start},{c.end},true")
    (target / "campaign_calendar.csv").write_text("\n".join(lines) + "\n", encoding="utf-8")
    manifest = {"is_synthetic": True, "scenario": data.scenario, "seed": seed,
                "as_of": data.as_of.isoformat(),
                "params_version": SEED_PARAMS_VERSION, "window_days": WINDOW_DAYS, "row_counts": counts,
                "injected_lag_days": INJECTED_LAG_DAYS if data.scenario == "lag3" else None}
    (target / "manifest.json").write_text(json.dumps(manifest, indent=1), encoding="utf-8")
    return target


def main() -> None:
    ap = argparse.ArgumentParser(description="Gera dados SINTÉTICOS locais (nada é gravado no BigQuery).")
    ap.add_argument("--scenario", choices=["realistic", "lag3", "both"], default="both")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--as-of", type=date.fromisoformat, default=DEFAULT_AS_OF)
    ap.add_argument("--out", default="data/synthetic")
    args = ap.parse_args()
    for sc in (["realistic", "lag3"] if args.scenario == "both" else [args.scenario]):
        path = write(generate(sc, args.as_of, args.seed), Path(args.out), args.seed)
        print(f"[{sc}] {path}: {(path / 'manifest.json').read_text(encoding='utf-8')[:0]}ok")


if __name__ == "__main__":
    main()
