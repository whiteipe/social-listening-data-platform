import pytest

from src.common.relevance import match_groups


@pytest.mark.parametrize("text, expected", [
    ("Review da operadora Vivo em 2026", ["marca"]),
    ("Vivo Fibra 1 giga: vale a pena?", ["marca"]),
    ("Telefônica Vivo anuncia 5G", ["marca"]),
    ("Claro Net ou operadora TIM?", ["concorrente_a", "concorrente_b"]),
    ("TIM Controle x Vivo Fibra", ["marca", "concorrente_b"]),
    ("Tutorial tim live fish video", []),
    ("Show AO VIVO hoje", []),
    ("Claro que sim, vamos nessa", []),
    ("Tim Maia no palco", []),
    ("", []),
    (None, []),
])
def test_match_groups(text, expected):
    assert sorted(match_groups(text)) == sorted(expected)
