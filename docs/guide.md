# Guide

Complete files for the common ways to use `forktex-fsd`. Each block starts with
the path it belongs at. The exact behaviour of every name used here is in the
[reference](reference.md).

- [Before you start](#before-you-start)
- [Your first fsd.toml](#your-first-fsdtoml)
- [Bind a service](#bind-a-service)
- [Bind any stack](#bind-any-stack)
- [Add your own atoms](#add-your-own-atoms)
- [Pass arguments to an atom](#pass-arguments-to-an-atom)
- [Gate pull requests](#gate-pull-requests)
- [Keep a report](#keep-a-report)
- [Use it from Python](#use-it-from-python)

## Before you start

Install the command once per machine:

```bash
uv tool install forktex-fsd      # or: pipx install forktex-fsd
```

To use it from Python, add `forktex-fsd` to your project's dependencies instead.

`fsd` finds `fsd.toml` in the current directory or the nearest one above it, as
git finds `.git`. `fsd -C DIR …` starts the search from somewhere else.

## Your first fsd.toml

A Python library, bound to the commands it already uses:

```toml
# fsd.toml
standard = "1.0"
profile  = "library"

[operation]
setup = "poetry install"
clean = "git clean -fdX"

[assurance]
format   = "poetry run ruff format --check ."
lint     = "poetry run ruff check ."
validate = "poetry run pyright"
test     = "poetry run pytest -q"

[security]
audit = "poetry run pip-audit"

[delivery]
build   = "poetry build"
publish = "poetry publish"

[documentation]
manual = { file = ["README.md", "AGENTS.md"] }
```

Then see where it stands:

```bash
fsd
```

```
┌─ my-lib · library · FSD 1.0.0 ───────────────────────────────────────── compliant ─┐
│        atom         kind     strength   status    binding                          │
├─ assurance ────────────────────────────────────────────────────────────────────────┤
│  ok    format     standard     must      bound    poetry run ruff format --check . │
│  ok    lint       standard     must      bound    poetry run ruff check .          │
│  ok    validate   standard    should     bound    poetry run pyright               │
│  ok    test       standard     must      bound    poetry run pytest -q             │
│ warn   license    standard    should    unbound   —                                │
│ …                                                                                  │
└────────────────────────────────────────────────────────────────────────────────────┘
```

A `must` atom left unbound fails its track. A `should` atom left unbound is a
warning. A track is compliant when none of its `must` atoms is a gap. Which
atoms are which depends on the profile; `fsd help` shows every one.

A `must` that does not apply is declared, with the reason:

```toml
[delivery]
publish = { na = "an internal tool, installed from the repository" }
```

## Bind a service

A service is started, watched, stopped and deployed, so those atoms are `must`:

```toml
# fsd.toml
standard = "1.0"
profile  = "service"

[operation]
setup  = "docker compose build"
start  = "docker compose up -d --wait"
stop   = "docker compose down"
status = ["docker compose ps", "docker compose logs --tail 50"]

[assurance]
format = "docker compose run --rm api ruff format --check ."
lint   = "docker compose run --rm api ruff check ."
test   = "docker compose run --rm api pytest -q"

[security]
audit = "docker compose run --rm api pip-audit"

[delivery]
build    = "docker build -t registry.example.com/api:latest ."
deploy   = "./deploy.sh production"
rollback = "./deploy.sh production --previous"

[documentation]
manual = { file = ["README.md", "AGENTS.md", "CONTRIBUTING.md"] }
```

`status` is the state of what `start` brought up and its recent output, as
`systemctl status` shows. `fsd report` runs `start`, `status` and `stop` as one
bracket, so `status` is read while the service is up, and `stop` runs whatever
happened in between.

## Bind any stack

The standard names no tool, so a TypeScript application binds the same atoms:

```toml
# fsd.toml
standard = "1.0"
profile  = "application"

[operation]
setup = "npm ci"
clean = "npx rimraf dist coverage"

[assurance]
format   = "npx prettier --check ."
lint     = "npx eslint ."
validate = "npx tsc --noEmit"
test     = "npx vitest run"
license  = "pipx run reuse lint"

[security]
audit = "npm audit --audit-level=high"

[delivery]
build   = "npm run build"
install = "npm install --global ."
publish = { na = "installed from the repository" }

[documentation]
manual = { file = "README.md" }
```

An `application` must say how it is installed onto a machine (`install`). A
`library` must say how it is published, and a `service` how it is deployed.

## Add your own atoms

Any name the standard does not define, written under a track, is a custom atom
of that track:

```toml
[operation]
migrate = "alembic upgrade head"
seed    = "python -m app.seed"

[assurance]
contracts = "schemathesis run openapi.json"
```

```bash
fsd migrate
fsd contracts
```

A custom atom is always a command. It may not be called `run`, `help` or
`report`, which are `fsd`'s own commands. It appears in the compliance table
marked `custom` and never counts for or against compliance. A custom atom under
`[assurance]`, `[security]` or `[documentation]` runs with its track, after the
track's standard atoms. So `contracts` above runs in every `fsd assurance`.

## Pass arguments to an atom

Everything after the atom's name goes to its command. With no placeholder, the
arguments follow the last command:

```toml
[assurance]
test = "pytest -q"                          # fsd test -k smoke → pytest -q -k smoke
```

Where they belong elsewhere, `{args}` says so. With no arguments, it is removed:

```toml
[operation]
start = "docker compose up {args} --wait"   # fsd start api → docker compose up api --wait
```

A list is commands run in order, and the first failure stops it. Arguments go
to every step that says `{args}`, and to no other. A list in which no step says
`{args}` takes no arguments, since `fsd` would only be guessing which command
they are for:

```toml
[assurance]
lint = ["ruff check {args}", "lint-imports"]   # fsd lint src/x → ruff check src/x, then lint-imports
```

Each argument is quoted for the shell where `{args}` stands, so `fsd lint
'$(rm -rf ~)'` passes text, not a command. Never put quotes around `{args}`
yourself: inside `"…"` the shell expands it again.

## Gate pull requests

The workflow installs the toolchain and asks `fsd`. The commands themselves
live only in `fsd.toml`:

```yaml
# .github/workflows/gate.yml
name: gate

on:
  push:
    branches: [main]
  pull_request:

jobs:
  gate:
    strategy:
      matrix:
        os: [ubuntu-latest, macos-latest, windows-latest]
    runs-on: ${{ matrix.os }}
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v6
      - run: uv tool install forktex-fsd
      - run: fsd setup
      - run: fsd assurance
      - run: fsd security
      - run: fsd documentation
      - run: fsd build
```

The gate is the tracks whose atoms check rather than act: assurance, security
and documentation, one step each, so a failure names its track. Each track
first checks its own compliance and runs nothing
if a `must` atom is unbound: a gate that ran only what happens to be bound would
pass a repository with no tests. Then it runs the track's atoms in the
standard's order, its custom atoms after them, and stops at the first failure.
It exits 0 when everything passed, 1 when compliance or an atom failed, and 2
when `fsd.toml` is invalid or the command was used wrongly.

To run everything routine in one command without stopping at a failure, use
`fsd report` (see [Keep a report](#keep-a-report)); it exits 1 when anything
failed, so it can gate too.

Operation and delivery act rather than check, so they never run as a whole:
`fsd delivery` is refused, and `fsd build` or `fsd publish` is named on its own.

## Keep a report

`fsd report` runs every routine atom and does not stop at a failure. Routine
atoms are those that are read-only or stay in the workspace, and `clean` is left
out. For each atom, `fsd report` keeps the commands, the exit code, the start
time, the duration and the last 60 lines of output.

A binding names the result files its commands write, and the report reads them:

```toml
[assurance]
test = { run = "pytest -q --junitxml=build/junit.xml --cov --cov-report=xml:build/coverage.xml", results = ["build/junit.xml", "build/coverage.xml"] }
lint = { run = "ruff check . --output-format sarif -o build/ruff.sarif", results = ["build/ruff.sarif"] }
```

| Format | Read as |
|---|---|
| JUnit XML | tests, failures, errors, skipped |
| Cobertura XML | line and branch coverage |
| SARIF (`.sarif`, `.sarif.json`) | findings |
| anything else | linked as an artifact |

It prints the compliance table and the report table. It also writes
`fsd-report.json`, the data with camelCase keys and UTC times, and
`fsd-report.md`, which includes the output of every failing atom. To keep them
from every CI run:

```yaml
      - run: fsd report
      - uses: actions/upload-artifact@v4
        if: always()
        with:
          name: fsd-report-${{ matrix.os }}
          path: fsd-report.*
```

## Use it from Python

`Project` is the one entry point. It reads `fsd.toml` against the standard this
version ships:

```python
# compliance.py
import sys
from pathlib import Path

from forktex_fsd import Project, ProjectNotFoundError


def main(workspace: Path) -> int:
    worst = 0
    for repo in sorted(p for p in workspace.iterdir() if p.is_dir()):
        try:
            project = Project.load(repo)
        except ProjectNotFoundError:
            print(f"{repo.name:24} no fsd.toml")
            continue
        compliance = project.check()
        gaps = [f"{t.track}: {', '.join(a.atom for a in t.failures)}" for t in compliance.tracks if t.failures]
        print(f"{repo.name:24} {project.profile:12} {'; '.join(gaps) or 'compliant'}")
        worst = max(worst, 0 if compliance.compliant else 1)
    return worst


if __name__ == "__main__":
    raise SystemExit(main(Path(sys.argv[1])))
```

`check()` executes nothing. `run()` and `report()` execute the bindings, and
their output goes to `on_output` when you pass one:

```python
# nightly.py
from pathlib import Path

from forktex_fsd import Project

project = Project.find()
lines: list[str] = []

for result in project.run("test", "-x", on_output=lines.append):
    print(result.atom, result.outcome, result.detail)

report = project.report(on_output=lines.append)
Path("fsd-report.md").write_text(report.to_markdown(), encoding="utf-8")
print("passed" if report.passed else "failed")
```

Every error is a `forktex.error.AppError` with a code and `details`, so a
service maps it as it maps its own. The [reference](reference.md#errors) lists
them.
