"""Relevância por grupo: decide a quais grupos (marca/concorrentes) um texto pertence."""
import re
from functools import lru_cache

from src.common.config import _cfg


@lru_cache(maxsize=1)
def _compiled(key: str) -> dict[str, re.Pattern]:
    return {g: re.compile(rx) for g, rx in _cfg().get(key, {}).items()}


def match_groups(text: str | None, loose_group: str | None = None) -> list[str]:
    """Grupos cujo regex casa com o texto (pode ser mais de um: vídeos comparativos).

    `loose_group` aceita também o regex solto desse grupo; use só quando a busca na fonte
    já delimita o assunto (ex.: notícias).
    """
    if not text:
        return []
    groups = [g for g, rx in _compiled("match").items() if rx.search(text)]
    if loose_group and loose_group not in groups:
        rx = _compiled("match_loose").get(loose_group)
        if rx and rx.search(text):
            groups.append(loose_group)
    return groups
