import importlib

import pytest

from src.cli import COLLECTORS

IMPLEMENTED = {"youtube", "google_news", "trends"}
STUBS = [n for n in COLLECTORS if n not in IMPLEMENTED]


@pytest.mark.parametrize("name", list(COLLECTORS))
def test_collector_exposes_contract(name):
    mod = importlib.import_module(COLLECTORS[name])
    assert mod.TABLE in {"mentions", "social_daily", "trends_daily"}
    assert callable(mod.collect)


@pytest.mark.parametrize("name", STUBS)
def test_out_of_scope_collectors_are_stubs(name):
    """Reddit, X e Instagram ficam fora da v1 (decisão registrada na spec)."""
    with pytest.raises(NotImplementedError):
        importlib.import_module(COLLECTORS[name]).collect()
