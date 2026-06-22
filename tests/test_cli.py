"""The CLI entrypoint runs a full series and reports an exit code."""

from cop_thief.main import main


def test_cli_run_returns_zero(capsys):
    assert main(["run", "--no-log"]) == 0
    out = capsys.readouterr().out
    assert "Totals:" in out
    assert "Report written to" in out


def test_cli_defaults_to_run_when_no_subcommand(capsys):
    assert main(["--no-log"]) == 0
    assert "Totals:" in capsys.readouterr().out
