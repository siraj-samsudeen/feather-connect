"""Lists printed as a table: the headings first, the columns two spaces apart, no space at a line's end."""

from collections.abc import Sequence
from typing import TextIO


def print_table(lines: Sequence[Sequence[str]], out: TextIO) -> None:
    """Print `lines`, the headings first, each column as wide as its widest cell but the last."""
    widths = [max(len(line[column]) for line in lines) for column in range(len(lines[0]) - 1)]
    for line in lines:
        cells = [cell.ljust(width) for cell, width in zip(line[:-1], widths, strict=True)]
        print("  ".join([*cells, line[-1]]).rstrip(), file=out)
