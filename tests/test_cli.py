import json

from typer.testing import CliRunner

from src import cli

runner = CliRunner()


def test_collect_dry_run_writes_jsonl(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    fake = type("M", (), {"TABLE": "mentions", "collect": staticmethod(lambda days: [{"a": 1}])})
    monkeypatch.setattr(cli.importlib, "import_module", lambda name: fake)
    res = runner.invoke(cli.app, ["collect", "youtube", "--dry-run"])
    assert res.exit_code == 0, res.output
    lines = (tmp_path / "data/dry_run/youtube.jsonl").read_text(encoding="utf-8").splitlines()
    assert [json.loads(x) for x in lines] == [{"a": 1}]


def test_collect_unknown_source_fails():
    assert runner.invoke(cli.app, ["collect", "nope"]).exit_code != 0
