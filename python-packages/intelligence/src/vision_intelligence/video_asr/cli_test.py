from typer.testing import CliRunner

from vision_intelligence.video_asr.cli import app

runner = CliRunner()


def test_help_lists_all_subcommands():
    r = runner.invoke(app, ["--help"])
    assert r.exit_code == 0
    for cmd in ("run", "status", "rerun", "search", "export"):
        assert cmd in r.stdout
