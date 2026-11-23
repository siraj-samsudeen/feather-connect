"""`scripts/trace_requirements.py` (from the process template): lists the catalogue's
requirement IDs that no spec names. Each test writes a catalogue and specs of its own."""

import subprocess
import sys
from pathlib import Path

import pytest
import trace_requirements

CATALOGUE = """| ID | Requirement | Milestone |
|---|---|---|
| R1.1 | A user signs in. | M1 |
| R1.2 | A user signs out. | M1 |
| R2.1 | A user uses an identity provider. | M2 |
"""


@pytest.fixture
def project(tmp_path: Path) -> Path:
    (tmp_path / "requirements.md").write_text(CATALOGUE, encoding="utf-8")
    spec = tmp_path / "specs" / "sign-in" / "spec.md"
    spec.parent.mkdir(parents=True)
    spec.write_text("# sign-in\n\nCovers R1.1.\n", encoding="utf-8")
    return tmp_path


def run(project: Path, *extra: str) -> int:
    return trace_requirements.main([str(project / "requirements.md"), "--specs", str(project / "specs"), *extra])


def test_names_every_requirement_no_spec_covers(project: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert run(project) == 0
    assert capsys.readouterr().out.splitlines() == [
        "1 of 3 requirements are named by a spec.",
        "  not covered: R1.2",
        "  not covered: R2.1",
    ]


def test_only_counts_the_lines_of_one_milestone(project: Path, capsys: pytest.CaptureFixture[str]) -> None:
    run(project, "--only", "| M1 |")
    assert capsys.readouterr().out.splitlines() == ["1 of 2 requirements are named by a spec.", "  not covered: R1.2"]


def test_strict_fails_when_one_is_not_covered(project: Path) -> None:
    assert run(project, "--strict") == 1


def test_strict_passes_when_every_one_is_covered(project: Path) -> None:
    (project / "specs" / "sign-in" / "spec.md").write_text("R1.1, R1.2 and R2.1.\n", encoding="utf-8")
    assert run(project, "--strict") == 0


def test_another_id_pattern(project: Path, capsys: pytest.CaptureFixture[str]) -> None:
    (project / "requirements.md").write_text("REQ-7 and REQ-8\n", encoding="utf-8")
    (project / "specs" / "sign-in" / "spec.md").write_text("REQ-7\n", encoding="utf-8")
    run(project, "--pattern", r"REQ-\d+")
    assert capsys.readouterr().out.splitlines()[-1] == "  not covered: REQ-8"


def test_runs_as_a_script(project: Path) -> None:
    script = Path(trace_requirements.__file__)
    done = subprocess.run(
        [sys.executable, str(script), str(project / "requirements.md"), "--specs", str(project / "specs"), "--strict"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert done.returncode == 1
    assert "not covered: R1.2" in done.stdout
