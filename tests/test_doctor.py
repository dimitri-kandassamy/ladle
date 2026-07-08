"""Tests for `ladle doctor --install`: dependency planning and the run flow.

The plan is unit-tested against a controlled dep list with the platform's
package manager monkeypatched, so results don't depend on the host OS.
"""

from __future__ import annotations

import types

import pytest

from ladle import doctor, ui

PIP = [doctor.sys.executable, "-m", "pip", "install"]


@pytest.fixture(autouse=True)
def _reset():
    ui.configure(color=False)
    doctor.required_failures.clear()
    doctor.missing_deps.clear()
    yield
    ui.configure()
    doctor.required_failures.clear()
    doctor.missing_deps.clear()


def _ok_result(_cmd, *a, **k):
    return types.SimpleNamespace(returncode=0)


# ---- plan_install ----------------------------------------------------------
def test_plan_brew_groups_system_then_pip(monkeypatch):
    monkeypatch.setattr(doctor, "_system_manager", lambda: ("brew", "brew"))
    deps = [
        doctor.Dep("pandoc", brew=["pandoc"]),
        doctor.Dep("poppler", brew=["poppler"], apt=["poppler-utils"]),
        doctor.Dep("weasyprint", pip=["weasyprint"]),
    ]
    plan = doctor.plan_install(deps)
    assert plan.commands == [["brew", "install", "pandoc", "poppler"], [*PIP, "weasyprint"]]
    assert plan.manual == []


def test_plan_apt_uses_sudo(monkeypatch):
    monkeypatch.setattr(doctor, "_system_manager", lambda: ("apt", "apt-get"))
    plan = doctor.plan_install([doctor.Dep("poppler", brew=["poppler"], apt=["poppler-utils"])])
    assert plan.commands == [["sudo", "apt-get", "install", "-y", "poppler-utils"]]


def test_plan_apt_marks_brew_only_dep_manual(monkeypatch):
    # pandoc has no apt channel (distro build lags) -> can't auto-install on apt.
    monkeypatch.setattr(doctor, "_system_manager", lambda: ("apt", "apt-get"))
    plan = doctor.plan_install([doctor.Dep("pandoc", brew=["pandoc"])])
    assert plan.commands == []
    assert plan.manual == ["pandoc"]


def test_plan_no_manager_system_manual_pip_still_runs(monkeypatch):
    monkeypatch.setattr(doctor, "_system_manager", lambda: None)
    deps = [doctor.Dep("poppler", brew=["poppler"], apt=["poppler-utils"]), doctor.Dep("wp", pip=["weasyprint"])]
    plan = doctor.plan_install(deps)
    assert plan.manual == ["poppler"]
    assert plan.commands == [[*PIP, "weasyprint"]]


# ---- do_install ------------------------------------------------------------
def test_do_install_runs_commands_when_confirmed(monkeypatch):
    monkeypatch.setattr(doctor, "_system_manager", lambda: ("brew", "brew"))
    monkeypatch.setattr(doctor, "run_checks", lambda: None)  # don't re-probe the real host
    calls = []
    monkeypatch.setattr(doctor.subprocess, "run", lambda cmd, *a, **k: calls.append(cmd) or _ok_result(cmd))
    doctor.missing_deps[:] = [doctor.Dep("poppler", brew=["poppler"])]

    doctor.do_install(assume_yes=True)  # --yes: no prompt

    assert calls == [["brew", "install", "poppler"]]


def test_do_install_non_interactive_without_yes_skips(monkeypatch, capsys):
    monkeypatch.setattr(doctor, "_system_manager", lambda: ("brew", "brew"))
    monkeypatch.setattr(ui.sys.stdin, "isatty", lambda: False)  # can't prompt
    monkeypatch.setattr(doctor.subprocess, "run", lambda *a, **k: pytest.fail("must not run"))
    doctor.missing_deps[:] = [doctor.Dep("poppler", brew=["poppler"])]

    doctor.do_install(assume_yes=False)

    assert "re-run with --yes" in capsys.readouterr().err


def test_do_install_reports_failed_command(monkeypatch, capsys):
    monkeypatch.setattr(doctor, "_system_manager", lambda: ("brew", "brew"))
    monkeypatch.setattr(doctor, "run_checks", lambda: None)
    monkeypatch.setattr(doctor.subprocess, "run", lambda *a, **k: types.SimpleNamespace(returncode=1))
    doctor.missing_deps[:] = [doctor.Dep("poppler", brew=["poppler"])]

    doctor.do_install(assume_yes=True)

    assert "command failed" in capsys.readouterr().err


# ---- main dispatch ---------------------------------------------------------
def test_main_calls_install_when_missing(monkeypatch):
    def fake_checks():
        doctor.required_failures[:] = ["missing: pdfinfo"]
        doctor.missing_deps[:] = [doctor.Dep("poppler", brew=["poppler"])]

    monkeypatch.setattr(doctor, "run_checks", fake_checks)
    seen = {}
    monkeypatch.setattr(doctor, "do_install", lambda **kw: seen.update(kw))

    code = doctor.main(["--install"])

    assert seen == {"assume_yes": False}
    assert code == 1  # still failing (stubbed install fixed nothing)


def test_main_without_install_never_installs(monkeypatch):
    def fake_checks():
        doctor.required_failures[:] = ["x"]
        doctor.missing_deps[:] = [doctor.Dep("poppler", brew=["poppler"])]

    monkeypatch.setattr(doctor, "run_checks", fake_checks)
    monkeypatch.setattr(doctor, "do_install", lambda **kw: pytest.fail("must not install"))

    assert doctor.main([]) == 1


def test_main_clean_returns_zero(monkeypatch):
    monkeypatch.setattr(doctor, "run_checks", lambda: None)  # nothing missing
    assert doctor.main(["--install", "--yes"]) == 0
