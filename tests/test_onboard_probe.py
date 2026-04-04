"""Regression coverage for Python-path reporting in bootstrap probes."""

from __future__ import annotations

from tools import onboard_probe as probe


def test_reported_python_path_preserves_venv_executable(monkeypatch, tmp_path):
    venv_root = tmp_path / ".venv"
    venv_python = venv_root / "Scripts" / "python.exe"

    monkeypatch.setattr(probe.sys, "executable", str(venv_python))
    monkeypatch.setattr(probe.sys, "prefix", str(venv_root))
    monkeypatch.setattr(probe.sys, "base_prefix", str(tmp_path / "python-base"))

    assert probe.running_in_virtualenv() is True
    assert probe.reported_python_path() == str(venv_python)


def test_reported_python_path_resolves_non_venv_interpreter(monkeypatch, tmp_path):
    python_root = tmp_path / "python-base"
    python_path = python_root / "bin" / "python"
    python_path.parent.mkdir(parents=True, exist_ok=True)
    python_path.write_text("", encoding="utf-8")

    monkeypatch.setattr(probe.sys, "executable", str(python_path))
    monkeypatch.setattr(probe.sys, "prefix", str(python_root))
    monkeypatch.setattr(probe.sys, "base_prefix", str(python_root))

    assert probe.running_in_virtualenv() is False
    assert probe.reported_python_path() == str(python_path.resolve())


def test_collect_probe_uses_reported_python_path(monkeypatch, tmp_path):
    fake_python = str(tmp_path / ".venv" / "Scripts" / "python.exe")

    monkeypatch.setattr(probe, "reported_python_path", lambda: fake_python)
    monkeypatch.setattr(
        probe,
        "package_versions",
        lambda: {name: "MISSING" for name in probe.PACKAGE_NAMES},
    )
    monkeypatch.setattr(probe, "detect_psql", lambda home: "")
    monkeypatch.setattr(probe, "detect_pdflatex", lambda: "")
    monkeypatch.setattr(probe, "detect_r", lambda: "")
    monkeypatch.setattr(probe, "detect_bash", lambda: "")
    monkeypatch.setattr(probe, "which", lambda name: "")
    monkeypatch.setattr(
        probe,
        "local_state_records",
        lambda repo: {
            "config_dir": "",
            "state_dir": "",
            "storage_hint": {"kind": "local_or_unknown", "provider": ""},
            "files": {},
        },
    )

    result = probe.collect_probe()

    assert result["python"]["path"] == fake_python
    assert result["python"]["pip_command"] == f'"{fake_python}" -m pip'
    assert "bibtex" in result["tools"]


def test_detect_bibtex_prefers_pdflatex_sibling(tmp_path):
    tex_dir = tmp_path / "tex"
    tex_dir.mkdir()
    pdflatex = tex_dir / "pdflatex.exe"
    bibtex = tex_dir / "bibtex.exe"
    pdflatex.write_text("", encoding="utf-8")
    bibtex.write_text("", encoding="utf-8")

    assert probe.detect_bibtex(str(pdflatex)) == str(bibtex)
