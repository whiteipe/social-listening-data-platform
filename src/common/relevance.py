"""Relevância por grupo: decide a quais grupos (marca/concorrentes) um texto pertence."""
import re
from functools import lru_cache

from src.common.config import _cfg


@lru_cache(maxsize=1)
def _compiled(key: str) -> dict[str, re.Pattern]:
    return {g: re.compile(rx) for g, rx in _cfg().get(key, {}).items()}


@lru_cache(maxsize=1)
def _context() -> re.Pattern | None:
    rx = _cfg().get("context")
    return re.compile(rx) if rx else None


def match_groups(text: str | None, loose_group: str | None = None) -> list[str]:
    """Grupos a que o texto pertence (pode ser mais de um: vídeos comparativos).

    Um grupo vale se (a) o regex estrito `match` casa, ou (b) a marca "solta" (`match_loose`)
    casa E o texto tem uma palavra de contexto de telecom (`context`), em qualquer posição.
    `loose_group` aceita a marca solta desse grupo SEM exigir contexto; use só quando a busca
    na fonte já delimita o assunto (ex.: notícias).
    """
    if not text:
        return []
    groups = [g for g, rx in _compiled("match").items() if rx.search(text)]
    ctx = _context()
    has_context = bool(ctx and ctx.search(text))
    for g, rx in _compiled("match_loose").items():
        if g in groups or not rx.search(text):
            continue
        if has_context or g == loose_group:
            groups.append(g)
    return groups
