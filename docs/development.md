# Developing `forktex-fsd`

## Architecture

Library modules, with the command line and its renderer on top. Imports go in
one direction only: the import contract in `pyproject.toml` fails `fsd lint` on
any import upward.

```
_cli               the `fsd` script: parses arguments, calls Project, maps outcomes to exit codes
_render            boxed tables for the project, the standard, one atom and a report
project            Project: the one entry point, a repository and its standard
report             runs every routine atom and keeps the evidence; Report, as JSON and Markdown
check | run        compliance (executes nothing) · execution (executes bindings)
binding | results  fsd.toml → Bindings · result files (JUnit, Cobertura, SARIF) read by format
standard           standard.toml → Standard: the general contracts
errors             FsdError and the errors derived from it
```

The command line imports the package's public names and its own renderer,
nothing else. So anything it does, a consumer can do through `Project` without
it. The modules starting with `_` are not part of the public surface. Neither is
any name a module exports that the package root does not.

## Decisions worth knowing

- **The standard is data.** `standard.toml` ships in the wheel and is the only
  place an atom, contract or strength is defined. Changing it is changing the
  standard: bump its `version` and record it in this repository's changelog. Contracts
  name no tool.
- **Compliance is per track.** There is no overall level. A single level let a
  repository strong on one axis read as mature while a whole axis was empty.
- **Presence, not execution.** `check` proves an atom is bound, never that the
  binding works. The legacy FSD showed the cost of pretending otherwise: a
  target whose body was `echo` scored as satisfied. `run` is where a binding is
  proven, and it is opt-in.
- **Every command runs through the shell; a list is steps.** This follows mise
  and Taskfile: a string is one command, a list is commands in order. It is the
  form simplest to read and to patch, at the cost of shell syntax differing
  between `sh` and `cmd` — portable bindings call a program (`poetry run …`,
  `python scripts/…`) rather than relying on shell features.
- **Custom atoms extend a track, not the standard.** An unknown name under a
  track is the repository's own atom: runnable, reported, never scored. Under
  a checks track it runs with that track, so a gate can grow without a new
  version of the standard.
- **The command line answers to atoms directly.** `fsd test` runs `test`; fsd's
  own options come first, so everything after an atom's name is its arguments
  (`fsd start api --watch`). Commands, tracks and atoms share one namespace, so
  a custom atom may take none of their names. `fsd.toml` is found by
  searching upward, as git finds `.git`; `-C DIR` starts the search elsewhere.
- **Tracks are the only grouping.** A track whose atoms all check (assurance,
  security, documentation) runs as a whole: `fsd assurance` checks that track's
  compliance, then runs its atoms in order and stops at the first failure. A
  gate is the checks tracks named in one line. There is no gate atom: an atom
  that ran other atoms would be a second grouping, and a binding that claimed
  to be the gate could drift from its parts.
- **Profiles follow how software reaches its user.** Consumed (library),
  installed (application), deployed (service) — the axis that decides which
  delivery and operation atoms apply. One profile per repository: its primary
  purpose, as SPDX records a package's primary purpose.
- **Effects grow outward**: read-only, local (workspace and processes), host (this
  machine beyond the workspace), external (the world). A checks track may hold
  only read-only and local atoms, and a report runs only those, so nothing run
  as a matter of course installs, publishes or deploys.
- **Built on the forktex substrate.** Errors are `forktex.error.AppError`
  subclasses carrying an `AppErrorCode`; values are `forktex.types`
  `BaseValueObject` (a closed variant refuses unknown keys in `fsd.toml`); the
  report is a `BaseWireValueObject` — camelCase JSON, timestamps as
  `UtcDateTime`; logging goes through `forktex.log.get_logger` behind a
  `NullHandler`, and the library never prints — a caller passes `on_output` to
  see command output. The substrate's infrastructure dependencies come along;
  whether to slim them into extras is an open question for `forktex`, not here.
- **Two exceptions to the ForkTex corpus, taken deliberately.** The corpus says
  a library ships no command line (`package-layout:no-cli-in-a-library`) and
  that a repository's gate is `make ci` (`gate:ci-is-one-command`). FSD is a
  tool whose purpose is to be run, so it ships `fsd`, kept apart from the
  library by the import contract; and its gate is `fsd assurance`,
  `fsd security` and `fsd documentation`, because a Makefile is the one runner
  that is not cross-platform. The corpus rules are
  to be amended to say so.
- **A report keeps going.** A track run stops at the first failure; `fsd report`
  runs every routine atom except `clean` (which would erase what `build` made),
  brackets a service's start → status → stop, and reads measurements only from
  formats every ecosystem writes — JUnit XML, Cobertura XML, SARIF.

## Commands

This repository is driven by its own `fsd.toml`; there is no Makefile.

```bash
poetry install --with dev     # once; afterwards `poetry run fsd setup` refreshes it
poetry run fsd                # every atom, its binding and compliance
poetry run fsd assurance      # format, lint (+ the import contract), types, tests at a
                              # 100% line and branch floor, licence headers, and the
                              # Linux platforms suite (Docker)
poetry run fsd security       # lock check and dependency audit
poetry run fsd documentation  # the manual's files exist
poetry run fsd build          # wheel + sdist, twine check, install-and-use smoke test
poetry run fsd report         # run every routine atom; write fsd-report.json and .md
poetry run fsd tidy           # rewrite formatting, fixable lint and licence headers
poetry run fsd publish        # release-check (clean tree, HEAD tagged v<version>), then upload
```

`.github/workflows/gate.yml` runs the gate and `fsd build` on Linux,
and `fsd test` and `fsd build` natively on macOS and Windows, which no
container can run. Distribution is PyPI only; users install with
`uv tool install forktex-fsd` or `pipx install forktex-fsd`.

## Tests

| Directory | Holds |
|---|---|
| `tests/usage/` | What a consumer does, through `Project` alone: one file per kind of repository or task. These include the README example, and a check that every example in the documentation is accepted. |
| `tests/contract/` | The rules, module by module: each binding form, each status, each error and its `details`, the renderer, the command line, and the public surface. |
| `tests/platforms/` | The built wheel, installed in a pinned container of each Linux userland a consumer runs (Debian with `dash`, Alpine with busybox and musl), passing every scenario of `tests/usage/` there. It is the custom assurance atom `platforms`, so part of `fsd assurance`, and needs a running Docker daemon. |

Commands are real subprocesses of the interpreter running the tests, so they
behave the same on every OS. Files are real files. The only stand-ins are for a
terminal: a stream that reports an encoding or a TTY. Line and branch coverage
are held at 100, because every branch here is a rule of the standard.

## Releasing

1. Move the `[Unreleased]` entries in `CHANGELOG.md` under the new version, dated.
2. Set `version` in `pyproject.toml`; commit; tag the commit `v<version>`.
3. `poetry run fsd assurance`, `fsd security`, `fsd documentation` and `fsd build`.
4. `poetry run fsd publish`, which refuses a dirty tree, an untagged `HEAD`, a
   missing changelog section or stale artefacts in `dist/`.
