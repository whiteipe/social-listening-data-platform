"""Notícias via Google News RSS (feed público, não oficial; sem chave nem cota declarada).

Limites conhecidos: ~100 itens por consulta, só título e link (redirecionamento do Google),
sem série de tom. Janela via operador `when:Nd`. Ver docs/LIMITATIONS.md.
"""
import hashlib
import re
import time
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import UTC
from email.utils import parsedate_to_datetime

import requests
from tenacity import retry, stop_after_attempt, wait_exponential

from src.common.config import load_locale, load_queries, settings
from src.common.log import log_event
from src.common.relevance import match_groups
from src.common.schema import make_row

TABLE = "mentions"
BASE = "https://news.google.com/rss/search"
HEADERS = {"User-Agent": "Mozilla/5.0 (brand-listening research)"}
SLEEP_S = 2  # educação com o servidor; o feed não publica limite


@retry(stop=stop_after_attempt(4), wait=wait_exponential(multiplier=2, max=60), reraise=True)
def _fetch(query: str, days: int) -> bytes:
    region, lang = load_locale()
    q = urllib.parse.quote(f"{query} when:{max(days, 1)}d")
    # hl = idioma-país da interface, gl = país da edição, ceid = país:idioma do feed
    r = requests.get(f"{BASE}?q={q}&hl={lang}-{region}&gl={region}&ceid={region}:{lang}",
                     headers=HEADERS, timeout=30)
    r.raise_for_status()
    return r.content


def _split_title(title: str) -> tuple[str, str | None]:
    """Google News concatena ' - Veículo' ao título."""
    m = re.match(r"^(.*)\s+-\s+([^-]+)$", title)
    return (m.group(1).strip(), m.group(2).strip()) if m else (title, None)


def collect(days: int = 2) -> list[dict]:
    rows, seen = [], set()
    for query_group, terms in load_queries().items():
        for term in terms:
            root = ET.fromstring(_fetch(term, days))
            items = root.findall(".//item")
            time.sleep(SLEEP_S)
            for it in items:
                title, outlet = _split_title(it.findtext("title") or "")
                link = it.findtext("link") or ""
                # Grupo = regex estrito do título, mais o regex solto do grupo buscado.
                for group in match_groups(title, loose_group=query_group):
                    key = (link, group)
                    if key in seen:
                        continue
                    seen.add(key)
                    ts = parsedate_to_datetime(it.findtext("pubDate")).astimezone(UTC)
                    rows.append(make_row(
                        source="news", mention_id=hashlib.sha1(f"{link}|{group}".encode()).hexdigest()[:16],
                        published_at=ts, text=title, url=link, query_group=group, language="pt",
                        metrics={"outlet": outlet}, salt=settings.salt))
            log_event("collect_term", source="google_news", term=term, items=len(items))
    log_event("collect_done", source="google_news", rows=len(rows))
    return rows
