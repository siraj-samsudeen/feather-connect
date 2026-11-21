# 0008. fcon as the technical name

- Status: accepted
- Date: 2026-11-21
- Decision-makers: the project owner
- Decided in: issue #13
- Supersedes: the package, command and settings names in [0002](0002-three-packages.md) and [0006](0006-settings-from-environment-variables.md); their decisions otherwise stand

## Context and Problem Statement

The packages, the command and the settings were named `feather`: `feather-connect`, `feather-server`,
`feather-cli`, the command `feather` and `FEATHER_*` settings. Another product starts with the same
word, and the names are long to type. Only the walking skeleton exists, so renaming costs one
mechanical change now and much more later.

## Considered Options

- `fc`: the shortest, but `fc`, `fc-server` and `fc-cli` are taken on PyPI, and the command `fc` is
  already a shell built-in (bash, zsh), a PowerShell alias (`Format-Custom`) and a Windows program
  (`fc.exe`), so `fc server` would never reach the product.
- `fconn`: every name free on PyPI, the bare one included.
- `fcon`: `fcon-sdk`, `fcon-server` and `fcon-cli` free on PyPI; the bare `fcon` belongs to an
  unrelated tool.
- Keep `feather`.

## Decision Outcome

Chosen option: "`fcon`", because it is short, starts with "fc", and keeps clear of the other
product. Packages and imports: `fcon-sdk` / `fcon_sdk` (flows write `import fcon_sdk as fc`),
`fcon-server` / `fcon_server`, `fcon-cli` / `fcon_cli`. The command is `fcon`; settings are
`FCON_*`. Everything technical added later takes the same name: the database schema, loggers,
cookies, container images. Text that people read keeps the product's name, Feather Connect, and
the repo keeps its name.

### Consequences

- Good, because the command and settings are short, and no name clashes with a shell, a system
  program or a published package.
- Bad, because the plain name `fcon` on PyPI is not ours: the SDK installs as `fcon-sdk`.
- Bad, because an existing `.env` with `FEATHER_*` lines must be written again
  (`uv run scripts/worktree_env.py <n>`, or by hand from `.env.example`).
- The development database's container, user, password and database names stay `feather`, so
  nobody's existing database breaks.
