"""Avalia variantes do filtro de relevância do YouTube contra rótulos manuais.

Uso: python -m scripts.eval_youtube_filter
Entrada: data/eval/youtube_corpus.json (local, não versionado: dados da API do YouTube) e
scripts/youtube_filter_labels.json (rótulos por id de vídeo). Ver docs/AVALIACAO_FILTRO_YOUTUBE.md.
"""
import json
import random
import re
from pathlib import Path

from src.common.config import _cfg

GROUPS = ["marca", "concorrente_a", "concorrente_b"]
CFG = _cfg()
STRICT = {g: re.compile(rx) for g, rx in CFG["match"].items()}
BARE = {g: re.compile(rx) for g, rx in CFG["match_loose"].items()}
CTX = re.compile(CFG["context"])
FOREIGN = re.compile(r"(?i)\b(colombia|colômbia|m[eé]xico|chile|per[uú]|argentina|guatemala|equador)\b")


def _text(v):
    return f'{v["title"]}. {v["desc"]}'


def f1_strict(v):
    return {g for g in GROUPS if STRICT[g].search(_text(v))}


def f2_two_factor(v):
    t = _text(v)
    ctx = bool(CTX.search(t))
    return {g for g in GROUPS if STRICT[g].search(t) or (ctx and BARE[g].search(t))}


def f3_bare_only(v):
    t = _text(v)
    return {g for g in GROUPS if STRICT[g].search(t) or BARE[g].search(t)}


def f4_title_brand(v):
    t = _text(v)
    ctx = bool(CTX.search(t))
    return {g for g in GROUPS if STRICT[g].search(t) or (ctx and BARE[g].search(v["title"]))}


def f5_no_foreign(v):
    return set() if FOREIGN.search(_text(v)) else f2_two_factor(v)


FILTERS = {"F1 estrito (qualificador colado)": f1_strict, "F2 dois fatores": f2_two_factor,
           "F3 marca solta, sem contexto": f3_bare_only, "F4 marca no título + contexto": f4_title_brand,
           "F5 dois fatores + exclui outros países": f5_no_foreign}


def score(fn, truth, corpus, idx):
    tp = fp = fn_ = 0
    for i in idx:
        pred, real = fn(corpus[i]), truth.get(corpus[i]["id"], set())
        tp += len(pred & real)
        fp += len(pred - real)
        fn_ += len(real - pred)
    p = tp / (tp + fp) if tp + fp else 0.0
    r = tp / (tp + fn_) if tp + fn_ else 0.0
    return tp, fp, fn_, p, r, (2 * p * r / (p + r) if p + r else 0.0)


def table(title, truth, corpus):
    idx = list(range(len(corpus)))
    print(f"\n== {title} (n={len(idx)} vídeos) ==")
    print(f'{"filtro":42} {"TP":>3} {"FP":>3} {"FN":>3} {"prec":>6} {"recall":>7} {"F1":>6}  IC95% F1')
    rng = random.Random(7)
    for name, fn in FILTERS.items():
        tp, fp, fn_, p, r, f = score(fn, truth, corpus, idx)
        b = sorted(score(fn, truth, corpus, [rng.choice(idx) for _ in idx])[5] for _ in range(1000))
        print(f"{name:42} {tp:3d} {fp:3d} {fn_:3d} {p:6.2f} {r:7.2f} {f:6.2f}  [{b[25]:.2f}, {b[975]:.2f}]")


def main():
    corpus = json.loads(Path("data/eval/youtube_corpus.json").read_text(encoding="utf-8"))
    labels = json.loads(Path("scripts/youtube_filter_labels.json").read_text(encoding="utf-8"))
    truth = {k: set(v) for k, v in labels["positivos"].items()}
    table("Rótulo principal", truth, corpus)
    alt = {**truth, **{k: set(v) for k, v in labels["ambiguos"].items()}}
    table("Rótulo alternativo (citação de passagem conta)", alt, corpus)


if __name__ == "__main__":
    main()
