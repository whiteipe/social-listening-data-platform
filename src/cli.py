import importlib
import json
from pathlib import Path

import typer

app = typer.Typer()
COLLECTORS = {
    "instagram_hashtag": "src.collectors.instagram_hashtag",
    "social_own": "src.collectors.social_own",
    "youtube": "src.collectors.youtube",
    "reddit": "src.collectors.reddit",
    "x_search": "src.collectors.x_search",
    "google_news": "src.collectors.google_news",
    "trends": "src.collectors.trends",
}


@app.command()
def collect(source: str, days: int = 2, dry_run: bool = False):
    """days=2 por padrão: reprocessa janela recente (plataformas revisam métricas)."""
    if source not in COLLECTORS:
        raise typer.BadParameter(f"fonte desconhecida: {source}. Opções: {', '.join(COLLECTORS)}")
    mod = importlib.import_module(COLLECTORS[source])
    rows = mod.collect(days=days)
    if dry_run:
        out = Path("data/dry_run")
        out.mkdir(parents=True, exist_ok=True)
        (out / f"{source}.jsonl").write_text(
            "\n".join(json.dumps(r, ensure_ascii=False) for r in rows), encoding="utf-8")
        typer.echo(f"[dry-run] {len(rows)} linhas em data/dry_run/{source}.jsonl")
    else:
        from src.common.bq import upsert
        typer.echo(f"{upsert(mod.TABLE, rows)} linhas gravadas em {mod.TABLE}")


@app.command()
def classify(limit: int = 2000):
    from src.nlp.classify import run
    typer.echo(f"{run(limit)} menções classificadas")


@app.command()
def alert():
    from src.alerts.slack_alert import run
    run()


if __name__ == "__main__":
    app()
