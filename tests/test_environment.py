"""Tiny installation checks; these never build the full demonstration dataset."""

import json
from pathlib import Path

import pytest

from careergraph import cli


def test_doctor_checks_installation_without_creating_database(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The normal diagnostic checks resources/dependencies without dataset side effects."""
    target: Path = tmp_path / "must-not-be-created" / "doctor.db"
    cli.main(["--db", str(target), "doctor"])
    result: dict = json.loads(capsys.readouterr().out)
    assert result["ok"] is True
    assert result["sqlite_window_functions"] is True
    assert all(package["ok"] for package in result["runtime_packages"])
    assert all(result["resources"].values())
    assert not target.parent.exists()


def test_doctor_returns_nonzero_for_mismatched_package(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """A broken exact runtime pin produces an actionable failing diagnostic."""
    monkeypatch.setattr(cli, "version", lambda name: "0.0.0")
    target: Path = tmp_path / "never-created.db"
    with pytest.raises(SystemExit) as error:
        cli.main(["--db", str(target), "doctor"])
    result: dict = json.loads(capsys.readouterr().out)
    assert error.value.code == 1
    assert result["ok"] is False
    assert any(not package["ok"] for package in result["runtime_packages"])
    assert not target.exists()
