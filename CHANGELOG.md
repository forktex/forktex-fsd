# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project uses
[Semantic Versioning](https://semver.org/).

## [1.0.0] - 2026-11-18

The first version of the standard and its checker.

### Added

- **The FSD standard 1.0**, as data in `standard.toml`: five tracks (operation,
  assurance, security, delivery, documentation) and eighteen technology-agnostic
  atoms. Each atom has a contract, an effect class (read-only, local, host,
  external), an evidence kind (command, file) and a strength per
  profile: `library` (consumed), `application` (installed), `service`
  (deployed). Notable atoms: `status`, the state and recent output of what
  `start` brought up; `install`, the built artifact onto this machine;
  `manual`, the files that show a person or an agent how to start. Assurance,
  security and documentation are checks tracks: their atoms check rather than
  act, so each runs as a whole, and together they are the gate.
- **`fsd.toml`**: a repository binds each atom to a command, a list of commands
  run in order, `{ run = …, results = [...] }`, one or several files, or
  `{ na = "reason" }`, under the section of the atom's track. Any other name
  under a track is a custom atom of that track: runnable, reported, never
  scored, and run with its track when that track is a checks track. A custom
  atom may not take a track's or a command's name. Paths stay inside
  the repository, and unknown keys are refused. `standard = "1.0"` names the
  version a file was written for; a checker reads every file of its own major
  version up to its own minor. The file is found by searching upward from the
  current directory.
- **`Project`**, the one entry point. `Project.find()` and `Project.load(root)`
  read `fsd.toml` against the shipped standard.
  - `.check()` returns `Compliance` per track and executes nothing. A missing
    `must` fails its track; a missing `should` is a warning.
  - `.run(name, *args)` executes a binding through the platform shell. Arguments
    go to every command that says `{args}`, or at the end of a single command;
    a list of several without the placeholder takes none. Given a checks track, it checks that
    track's compliance, then runs its atoms in order and stops at the first
    failure. Operation and delivery never run as a whole, so nothing that acts
    beyond the workspace runs unless named.
  - `.report()` runs every routine atom without stopping. It keeps evidence per
    atom (steps, exit code, UTC start, duration, output tail) and reads
    measurements from JUnit XML, Cobertura XML and SARIF. A service's `start`,
    `status` and `stop` run as one bracket, and a process `start` leaves
    running in the background does not hold the report open.
  - Output goes to an `on_output` callback when one is given; the library never
    prints.
- **The `fsd` command**:
  - bare `fsd` shows the repository as a boxed table;
  - `fsd <atom> [args...]` runs an atom;
  - `fsd <track>` runs one checks track; `fsd assurance`, `fsd security`
    and `fsd documentation` are the gate;
  - `fsd report` writes `fsd-report.json` and `fsd-report.md`;
  - `fsd help [atom] [--json]` shows the standard, or one atom's contract;
  - `-C DIR` starts somewhere else.

  Exit codes: 0 passed, 1 not met, 2 invalid input.
- **Built on the `forktex` substrate**:
  - errors are `AppError` subclasses with codes and `details`
    (`BindingError`, `InvalidStandardError`, `ProjectNotFoundError`,
    `UnknownAtomError`, `UsageError`);
  - values are `BaseValueObject`;
  - the report is a wire object, with camelCase JSON and canonical UTC times;
  - logging goes through `forktex.log`, and the library never prints.
