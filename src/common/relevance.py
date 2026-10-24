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


def match_groups(text: str | None, loose_group: str | None = None, title: str | None = None) -> list[str]:
    """Grupos a que o texto pertence (pode ser mais de um: vídeos comparativos).

    Um grupo vale se (a) o regex estrito `match` casa no texto, ou (b) a marca "solta"
    (`match_loose`) casa no TÍTULO e o texto tem uma palavra de contexto de telecom (`context`).
    Sem `title`, o próprio texto faz o papel de título (fontes que só têm título, como notícias).
    Exigir a marca no título descarta quem cita as operadoras só de passagem na descrição.

    `loose_group` aceita a marca solta desse grupo SEM exigir contexto; use só quando a busca
    na fonte já delimita o assunto (ex.: notícias).

    Escolhido entre 5 variantes em 93 vídeos rotulados à mão (docs/AVALIACAO_FILTRO_YOUTUBE.md).
    """
    if not text:
        return []
    head = title if title is not None else text
    groups = [g for g, rx in _compiled("match").items() if rx.search(text)]
    ctx = _context()
    has_context = bool(ctx and ctx.search(text))
    for g, rx in _compiled("match_loose").items():
        if g in groups or not rx.search(head):
            continue
        if has_context or g == loose_group:
            groups.append(g)
    return groups
