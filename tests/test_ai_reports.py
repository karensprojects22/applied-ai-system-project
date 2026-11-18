"""The evidence scripts shown in the README must keep working (exit code 0 = all cases pass)."""

import runpy

import pytest


@pytest.mark.parametrize("script", ["guardrail_report.py", "demo_ai.py"])
def test_report_script_runs_and_succeeds(script, tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)  # logs go to a temporary folder, not the repo
    monkeypatch.syspath_prepend(str(__import__("pathlib").Path(__file__).resolve().parent.parent))
    try:
        runpy.run_path(str(__import__("pathlib").Path(__file__).resolve().parent.parent / script),
                       run_name="__main__")
    except SystemExit as exit_info:
        assert exit_info.code in (0, None)
    assert capsys.readouterr().out.strip()
