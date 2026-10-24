"""Google Trends via trendspyg (mantida; pytrends foi arquivado em abril de 2025).

engine="auto": tenta requisição direta (0,8 s) e só abre o Chrome headless se ela falhar (8,6 s),
então Chrome continua necessário no CI/Docker como reserva. Medido em 24/10/2026: dados idênticos.
O interesse é relativo (0 a 100), na escala do termo mais forte da consulta; por isso todos
os termos vão na MESMA chamada (2 a 5), mantendo-os comparáveis entre si. O valor muda se a
lista de termos mudar. O coletor nunca derruba o pipeline: em erro, loga e devolve vazio.
"""
from datetime import UTC, datetime

import trendspyg

from src.common.config import load_trends
from src.common.log import log_event

TABLE = "trends_daily"


def _timeframe(days: int) -> str:
    # Até ~90 dias o Trends devolve pontos diários; acima disso passa a semanal.
    return "today 3-m" if days <= 90 else "today 12-m"


def collect(days: int = 90) -> list[dict]:
    terms, geo = load_trends()
    terms = terms[:5]
    try:
        res = trendspyg.download_google_trends_comparison(
            terms, geo=geo, timeframe=_timeframe(days), output_format="dict", include_geo=False,
            engine="auto")
    except Exception as exc:  # noqa: BLE001 — dependência externa frágil
        log_event("collect_failed", source="trends", error=type(exc).__name__, detail=str(exc)[:200])
        return []
    rows, loaded = [], datetime.now(UTC).isoformat()
    for point in res.get("interest_over_time", []):
        if point.get("is_partial"):  # o ponto parcial seria gravado e depois revisado
            continue
        for term in terms:
            value = point["values"].get(term)
            if value is None:
                continue
            rows.append({"date": point["date"][:10], "term": term, "geo": geo,
                         "interest": int(value), "_loaded_at": loaded})
    log_event("collect_done", source="trends", rows=len(rows))
    return rows
