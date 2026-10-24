"""Menções públicas no YouTube (vídeos e comentários).

Cota (documentação do YouTube Data API v3): padrão de 10.000 unidades/dia,
search.list = 100, commentThreads.list = 1. Mantemos UNIT_BUDGET abaixo disso.

A busca do YouTube ignora aspas e devolve vídeos sem relação com a marca. Por isso só vira
menção o vídeo cujo título/descrição casa com o regex de algum grupo (config `match`), e só os
comentários desses vídeos são coletados (também economiza cota). Um vídeo comparativo é gravado
uma vez por grupo que casa, com mention_id `<id>|<grupo>`.
"""
import html
from datetime import UTC, datetime, timedelta

from dateutil import parser as dtp
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from src.common.config import load_locale, load_queries, settings
from src.common.log import log_event
from src.common.relevance import match_groups
from src.common.schema import make_row

TABLE = "mentions"
UNIT_BUDGET = 8000  # nunca estoure a cota diária
SEARCH_COST = 100
COMMENTS_COST = 1
VIDEOS_COST = 1  # videos.list: até 50 ids por chamada


def _foreign_videos(yt, ids: list[str], lang: str) -> set[str]:
    """Vídeos cujo idioma DECLARADO existe e difere do esperado. Sem idioma declarado, mantém."""
    if not ids:
        return set()
    res = yt.videos().list(part="snippet", id=",".join(ids)).execute()
    out = set()
    for v in res.get("items", []):
        sn = v["snippet"]
        declared = sn.get("defaultAudioLanguage") or sn.get("defaultLanguage")
        if declared and not declared.lower().startswith(lang):
            out.add(v["id"])
    return out


def collect(days: int = 1) -> list[dict]:
    yt = build("youtube", "v3", developerKey=settings.youtube_key, cache_discovery=False)
    region, lang = load_locale()
    after = (datetime.now(UTC) - timedelta(days=max(days, 1))).isoformat()
    units, rows, seen, skipped, foreign = 0, [], set(), 0, 0
    for _group, terms in load_queries().items():
        for term in terms:
            if units + SEARCH_COST > UNIT_BUDGET:
                log_event("quota_guard", source="youtube", units=units, budget=UNIT_BUDGET)
                return rows
            res = yt.search().list(q=term, part="snippet", type="video", order="date",
                                   publishedAfter=after, maxResults=25,
                                   regionCode=region, relevanceLanguage=lang).execute()
            units += SEARCH_COST
            items = res.get("items", [])
            wrong_lang = _foreign_videos(yt, [it["id"]["videoId"] for it in items], lang)
            units += VIDEOS_COST if items else 0
            for it in items:
                vid, sn = it["id"]["videoId"], it["snippet"]
                if vid in wrong_lang:
                    foreign += 1
                    continue
                text = html.unescape(f'{sn["title"]}. {sn.get("description", "")}')
                groups = match_groups(text)
                if not groups or vid in seen:
                    skipped += 0 if vid in seen else 1
                    continue
                seen.add(vid)
                for g in groups:
                    rows.append(make_row(
                        source="youtube_video", mention_id=f"{vid}|{g}",
                        published_at=dtp.parse(sn["publishedAt"]), text=text,
                        url=f"https://www.youtube.com/watch?v={vid}", query_group=g,
                        author_id=sn["channelId"], salt=settings.salt))
                if units + COMMENTS_COST > UNIT_BUDGET:
                    continue
                try:
                    cts = yt.commentThreads().list(part="snippet", videoId=vid, maxResults=100,
                                                   textFormat="plainText", order="time").execute()
                except HttpError:  # comentários desativados (a chamada também consome cota)
                    units += COMMENTS_COST
                    continue
                units += COMMENTS_COST
                for c in cts.get("items", []):
                    s = c["snippet"]["topLevelComment"]["snippet"]
                    likes = s.get("likeCount", 0)
                    for g in groups:
                        rows.append(make_row(
                            source="youtube_comment", mention_id=f"{c['id']}|{g}",
                            published_at=dtp.parse(s["publishedAt"]), text=s["textDisplay"],
                            url=f"https://www.youtube.com/watch?v={vid}&lc={c['id']}",
                            query_group=g, author_id=s.get("authorChannelId", {}).get("value"),
                            engagement=likes, metrics={"like_count": likes, "video_id": vid},
                            salt=settings.salt))
            log_event("collect_term", source="youtube", term=term, units=units,
                      videos_kept=len(seen), videos_dropped_irrelevant=skipped,
                      videos_dropped_language=foreign)
    log_event("collect_done", source="youtube", rows=len(rows), estimated_units=units)
    return rows
