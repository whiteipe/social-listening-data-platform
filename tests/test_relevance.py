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
    ("Internet de 1Gbps por R$79: minha experiência com Claro e Vivo", ["marca", "concorrente_a"]),
    ("CHIP CLARO GRÁTIS + INTERNET + LIGAÇÕES ILIMITADAS", ["concorrente_a"]),
    ("TIM Play mudou tudo: 9 streamings em um só pacote", ["concorrente_b"]),
    ("MELHOR PLANO DE INTERNET (TIM, CLARO E VIVO)", ["marca", "concorrente_a", "concorrente_b"]),
    ("ODEON E VIVO com problema no BTV: e agora?", []),
    ("Transmissão ao vivo do show de domingo, internet caiu", []),
    ("", []),
    (None, []),
])
def test_match_groups(text, expected):
    assert sorted(match_groups(text)) == sorted(expected)
