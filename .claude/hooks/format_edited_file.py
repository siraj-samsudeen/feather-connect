"""Formats and lints each Python file an agent edits, right after the edit (a Claude Code hook).

Claude Code runs this after every Edit or Write (.claude/settings.json, "PostToolUse") and passes
the tool call as JSON on stdin. For a `.py` file it runs `ruff format` and `ruff check --fix`.
When problems remain, it prints them and exits 2, so the agent sees them and fixes them now,
instead of at the end-of-change checks. Any other file is left alone. Standard library only.
"""

import json
import subprocess
import sys
from pathlib import Path

PROBLEMS_FOR_THE_AGENT = 2  # Claude Code shows a hook's stderr to the agent on exit code 2


def edited_file(hook_input: str) -> Path | None:
    """The file the tool call edited, or None when the input names no file."""
    try:
        path = json.loads(hook_input).get("tool_input", {}).get("file_path")
    except json.JSONDecodeError:
        return None
    return Path(path) if path else None


def ruff_is_installed() -> bool:
    """Whether `uv run ruff` works in this project (ruff is one of its dev dependencies)."""
    probe = subprocess.run(["uv", "run", "ruff", "--version"], capture_output=True, check=False)  # noqa: S607
    return probe.returncode == 0


def main() -> int:
    """Format and lint the edited file; 2 with the problems when some remain, else 0."""
    path = edited_file(sys.stdin.read())
    if path is None or path.suffix != ".py" or not path.exists():
        return 0
    if not ruff_is_installed():
        return 0  # a project without ruff: nothing to run, and nothing the agent can fix
    subprocess.run(["uv", "run", "ruff", "format", "--quiet", str(path)], check=False)  # noqa: S607
    check = subprocess.run(  # noqa: S607
        ["uv", "run", "ruff", "check", "--fix", "--quiet", str(path)], capture_output=True, text=True, check=False
    )
    if check.returncode != 0:
        print(check.stdout + check.stderr, file=sys.stderr)
        return PROBLEMS_FOR_THE_AGENT
    return 0


if __name__ == "__main__":
    sys.exit(main())
