# 0021. pyarrow reads and writes the record blocks

- Status: accepted
- Date: 2026-11-28
- Decision-makers: the project owner
- Decided in: issue #31, point 4 ("pyarrow comes with an ADR"); built in issue #35

## Context and Problem Statement

A version's records are kept as Parquet compressed with zstd (ADR 0023), so they keep their types
and DuckDB and Arrow can read them directly (R4.1, R4.2). The product needs a library that writes
and reads Parquet from Python 3.14 on Linux, Windows and macOS.

## Considered Options

- `pyarrow`, the Python library of the Apache Arrow project.
- `fastparquet`.
- Writing Parquet ourselves.

## Decision Outcome

Chosen option: `pyarrow`, because it is the reference implementation of Arrow and Parquet for
Python, written and released by the Apache Arrow project (Apache Software Foundation, Apache
License 2.0, several releases a year; 26.0.1 is the current one), with wheels for Python 3.14 on
every platform we build for, and zstd built in. It is the library DuckDB and the data tools of R4
exchange data through. `fastparquet` needs pandas and numpy and does less; writing Parquet
ourselves would be a format to maintain for nothing.

The package is real and maintained: published on PyPI as `pyarrow` by the Apache Arrow project
since 2016, with its source in the project's own repository, and installed and run on this
project's Python 3.14 by the speed prototype before it was added.

### Consequences

- Good, because blocks are typed and columnar, and later analysis reads them with no conversion.
- Bad, because the wheel is large (about 28 MB) and grows the container image.
- Bad, because a major release can change behaviour: the version is locked, and Dependabot
  proposes upgrades, tested by CI.
