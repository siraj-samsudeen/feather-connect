r"""Which catalogue requirements no spec covers yet (the `change-modes` skill, § Defaults).

A project that keeps a requirements catalogue gives each requirement an ID (for example R7.21),
and each spec names the IDs it covers, anywhere in its text. This script lists every ID in the
catalogue that no `spec.md` under `openspec/specs/` names, so "is the milestone done?" is a
report rather than a guess.

    python scripts/trace_requirements.py docs/requirements.md
    python scripts/trace_requirements.py docs/requirements.md --only M1 --strict

--pattern   the regular expression of an ID (default R\d+\.\d+)
--only      count only the catalogue lines that also contain this text (a milestone such as M1)
--strict    exit 1 when an ID is uncovered, for CI

Standard library only.
"""

import argparse
import re
import sys
from pathlib import Path


def catalogue_ids(text: str, pattern: re.Pattern[str], only: str | None) -> list[str]:
    """IDs in the order the catalogue first gives them, on the lines `only` keeps."""
    found: dict[str, None] = {}
    for line in text.splitlines():
        if only is not None and only not in line:
            continue
        for match in pattern.finditer(line):
            found.setdefault(match.group(0), None)
    return list(found)


def covered_ids(specs_dir: Path, pattern: re.Pattern[str]) -> set[str]:
    """The IDs that some `spec.md` under `specs_dir` names."""
    covered: set[str] = set()
    for spec in specs_dir.rglob("spec.md"):
        covered.update(m.group(0) for m in pattern.finditer(spec.read_text(encoding="utf-8")))
    return covered


def main(argv: list[str] | None = None) -> int:
    """Prints how many catalogue IDs a spec names and each one none does; 1 with --strict when any is missing, else 0."""
    parser = argparse.ArgumentParser(description="List catalogue requirements no spec covers.")
    parser.add_argument("catalogue", type=Path)
    parser.add_argument("--specs", type=Path, default=Path("openspec/specs"))
    parser.add_argument("--pattern", default=r"R\d+\.\d+")
    parser.add_argument("--only")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args(argv)

    pattern = re.compile(rf"\b{args.pattern}\b")
    ids = catalogue_ids(args.catalogue.read_text(encoding="utf-8"), pattern, args.only)
    covered = covered_ids(args.specs, pattern)
    missing = [i for i in ids if i not in covered]

    print(f"{len(ids) - len(missing)} of {len(ids)} requirements are named by a spec.")
    for i in missing:
        print(f"  not covered: {i}")
    return 1 if args.strict and missing else 0


if __name__ == "__main__":
    sys.exit(main())
