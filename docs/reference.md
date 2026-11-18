# Reference

Every public name, the standard, `fsd.toml`, the commands and the errors. The
[guide](guide.md) shows them in use.

- [Public surface](#public-surface)
- [`Project`](#project)
- [The standard](#the-standard)
- [`fsd.toml`](#fsdtoml)
- [Compliance](#compliance)
- [Running atoms](#running-atoms)
- [Reports](#reports)
- [The command line](#the-command-line)
- [Errors](#errors)

## Public surface

`forktex_fsd.__all__` is the contract. Everything else, including every module
whose name starts with `_`, is internal.

| Name | What it is |
|---|---|
| `Project` | The entry point: a repository and the standard it is held to. |
| `Standard`, `Track`, `Atom` | The standard, its tracks and its atoms. |
| `Profile`, `Strength`, `Effect`, `EvidenceKind` | The standard's vocabularies. |
| `Bindings` | One repository's `fsd.toml`, read against the standard. |
| `Binding`, `Command`, `FileBinding`, `NotApplicable`, `CustomAtom` | What an atom is bound to. |
| `Compliance`, `TrackCompliance`, `AtomCompliance`, `Status` | What `Project.check()` returns. |
| `RunResult`, `Outcome` | What `Project.run()` returns. |
| `Report`, `AtomEvidence`, `ResultFile`, `Format` | What `Project.report()` returns. |
| `FsdError`, `BindingError`, `InvalidStandardError`, `ProjectNotFoundError`, `UnknownAtomError`, `UsageError` | The errors. |
| `__version__` | The installed version. |

Every value is a pydantic model from `forktex.types` whose fields cannot be
reassigned. A model that holds a mapping, such as `Bindings.atoms`, is not
hashable, and that mapping is not a copy, so treat it as read-only. The results
of `check()` and `report()` serialise to camelCase JSON with
`model_dump_json()`, and read back with `model_validate_json()`.

## `Project`

```python
Project.find(start=None) -> Project
Project.load(root) -> Project
```

| Method | Returns | Meaning |
|---|---|---|
| `Project.find(start)` | `Project` | The project whose `fsd.toml` is in `start` (default: the working directory) or the nearest directory above it. Raises `ProjectNotFoundError`. |
| `Project.load(root)` | `Project` | The project whose `fsd.toml` is exactly in `root`. Raises `ProjectNotFoundError`, or `BindingError` when the file is invalid. |
| `.check()` | `Compliance` | Compliance per track. Executes nothing. |
| `.run(name, *args, on_output=None)` | `tuple[RunResult, ...]` | Runs one atom with `args`, or a checks track atom by atom until one fails. A track runs only when it is compliant; otherwise its one result is a failure naming its gaps. |
| `.report(*, on_output=None)` | `Report` | Runs every routine atom without stopping, and keeps the evidence. |
| `.binding(atom)` | `Binding \| None` | What `atom` is bound to here. |
| `.root`, `.profile`, `.custom` | | The repository root, its profile, its custom atoms. |
| `.standard`, `.bindings` | | The standard and the bindings it was read with. |

A project is held to the standard this version ships, `Standard.load()`.

`on_output` receives each line the commands print as it comes, ending in `\n`
(line endings are normalised), so `sys.stdout.write` prints it as a line. A
step's standard input is closed when its output is captured, so a command that
waits for input finishes instead of hanging. Without
it, `run()` leaves the output on the terminal, and `report()` keeps only the
tail in the evidence. The library itself never prints.

## The standard

Version 1.0.0. `fsd help` prints it; `fsd help <atom>` prints one contract in
full; `fsd help --json` gives it as data.

| Track | Atom | Effect | library | application | service | Contract, in short |
|---|---|---|---|---|---|---|
| operation | `setup` | local | must | must | must | Install everything needed to build and run it, from a fresh checkout. |
| | `start` | local | na | na | must | Run the software locally. |
| | `stop` | local | na | na | must | Tear down what `start` brought up. |
| | `status` | read-only | na | na | must | Whether it is running, with its recent output. |
| | `clean` | local | should | should | should | Remove everything the build and the run produced. |
| assurance | `format` | read-only | must | must | must | The source layout conforms to the project's style. |
| | `lint` | read-only | must | must | must | Static analysis fails on defects and unsafe patterns. |
| | `validate` | read-only | should | should | should | The source is shown statically to be consistent: types, schemas, contracts. |
| | `test` | local | must | must | must | The software's own tests pass. |
| | `license` | read-only | should | should | should | The licence is declared and applied to every source file. |
| security | `audit` | read-only | must | must | must | No dependency has a known vulnerability. |
| delivery | `build` | local | must | must | must | Turn the source into the deliverable artifact. |
| | `install` | host | na | must | na | Put the built artifact onto this machine. |
| | `publish` | external | must | should | should | Put a versioned artifact where its consumers fetch it. |
| | `deploy` | external | na | na | must | Put a version into a named environment where it runs. |
| | `rollback` | external | na | na | should | Return an environment to the version it ran before. |
| documentation | `manual` | read-only | must | must | must | A newcomer, a person or an agent, can start from the repository alone. |

| Vocabulary | Values |
|---|---|
| `Profile` | `library` (consumed), `application` (installed), `service` (deployed). One per repository: its primary purpose. |
| `Strength` | `must` (a gap fails the track), `should` (a gap is a warning), `na` (does not apply). |
| `Effect` | `read-only`, `local` (the workspace and its processes), `host` (this machine beyond the workspace), `external` (the world). Only the first two are routine: they run inside a track run and a report. |
| `EvidenceKind` | `command`, `file`. |
| `Track.checks` | `true` for assurance, security and documentation: their atoms check rather than act, so the track runs as a whole. Such a track holds only read-only and local atoms. |

`Standard` has `version`, `tracks`, `atoms`, `atom(name)` (raises
`UnknownAtomError`), `track(name)` (`None` when there is none), `in_track(track)`,
`major_minor`, and the classmethods `load()` and `parse(text)` (raises
`InvalidStandardError`). `Atom` has `name`, `track`, `contract`, `effect`,
`evidence`, `strength`, `composes` and `strength_for(profile)`.

## `fsd.toml`

```toml
# fsd.toml
standard = "1.0"            # the major.minor of the standard this file follows
profile  = "library"        # library | application | service

[assurance]
format = "ruff format --check ."                          # one command
lint   = ["ruff check .", "lint-imports"]                 # commands run in order
test   = { run = "pytest --junitxml=build/junit.xml", results = ["build/junit.xml"] }

[delivery]
publish = { na = "an internal tool" }                     # does not apply, and why

[documentation]
manual = { file = ["README.md", "AGENTS.md"] }            # files that must exist
```

| Form | Binds | Rules |
|---|---|---|
| `"command"` | a command atom, or a custom atom | Run through `sh`, or `cmd` on Windows. |
| `["a", "b"]` | the same | Run in order; the first failure stops the atom and is named. |
| `{ run = …, results = [...] }` | the same | `run` is either of the above. `results` are files the commands write, read by `fsd report`. |
| `{ file = "x" }`, `{ file = ["x", "y"] }` | a file atom (`manual`) | Every file must exist. Read back as `FileBinding.file`. |
| `{ na = "reason" }` | any standard atom | The reason is required, at least three characters long. Read back as `NotApplicable.na`. |

- Each atom sits under the section of its own track.
- Any other name under a track is a custom atom of that track. It must be a command, may appear under one track only, is named with letters, digits, `.`, `_` and `-` starting with a letter or digit, and may not take the name of a track or of an fsd command (`run`, `help`, `report`), since `fsd <name>` resolves them all in one namespace. A future minor version of the standard may add an atom of the same name as a custom one; the binding is then read as that atom, and refused if it sits under another track.
- Paths, in `file` and in `results`, are relative to the repository root and may not leave it; a link that resolves outside it counts as missing. `results` takes one path or a list.
- Unknown keys are refused, so a typo fails instead of vanishing.
- `standard` is the `major.minor` the file was written for. A checker reads a file of its own major version written for its minor or an earlier one, since a minor version of the standard only adds; any other file is refused.

## Compliance

| Name | Fields |
|---|---|
| `Compliance` | `standard`, `profile`, `tracks`, `compliant` |
| `TrackCompliance` | `track`, `atoms`, `failures`, `warnings`, `compliant` |
| `AtomCompliance` | `atom`, `strength` (`None` for a custom atom), `status`, `detail`, `custom`, `is_gap`, `is_failure`, `is_warning` |

| `Status` | Means | A gap? |
|---|---|---|
| `bound` | a command is bound | no |
| `present` | every bound file exists | no |
| `declared-na` | declared not to apply, with a reason | no |
| `na` | unbound, and the profile does not require it | no |
| `unbound` | nothing bound | yes |
| `missing-file` | a bound file does not exist | yes |

A gap on a `must` atom is a failure; on a `should` atom, a warning. A track is
compliant when it has no failures.

## Running atoms

| `RunResult` | |
|---|---|
| `atom` | the atom's name |
| `outcome` | `Outcome.PASSED`, `FAILED` or `SKIPPED` |
| `detail` | why: `exit code 3`, `step 2 of 3, exit code 1`, `na: <reason>`, `not bound`, `missing: <files>` |

- A file atom passes when its files exist.
- An unbound `must` atom fails. An unbound `should` atom is skipped, and so is one declared `na`.
- Arguments go to every command that says `{args}`, each quoted for the platform shell; never put quotes around `{args}`, or the shell reads inside them. A single command (a string, or a list of one) without it takes them at its end. A list of several commands in which none says `{args}` refuses arguments with `UsageError`.
- A command the shell cannot start, such as one longer than the system allows, fails its atom with `could not start: <reason>`.
- A checks track runs its standard atoms in order, then its custom atoms, and stops at the first failure.
- Arguments to an atom that is not a command, or to a track, raise `UsageError`; so does running operation or delivery as a whole.

## Reports

| `Report` | |
|---|---|
| `project` | the repository's directory name |
| `generated_at` | when, in UTC |
| `compliance` | a `Compliance` |
| `evidence` | one `AtomEvidence` per atom run, track by track in the standard's order. A checks track gives every atom, with its custom atoms after them; operation and delivery give their routine atoms but `clean`, with a service's `start`, `status` and `stop` run as one bracket: `status` only when `start` passed, `stop` whenever `start` ran |
| `passed` | compliant, and no atom failed |
| `to_markdown()` | the report as a Markdown page |

| `AtomEvidence` | |
|---|---|
| `atom`, `track`, `custom`, `outcome`, `detail` | as for a run |
| `steps`, `exit_code` | the commands run, and how the last one ended |
| `started_at`, `duration_seconds` | when, in UTC, and for how long |
| `output_tail` | the last 60 lines of output |
| `results` | one `ResultFile` per file the binding names: `path`, `format`, `values`, `summary` |

`Format` is `junit`, `cobertura`, `sarif`, `artifact` (any other file, or one
unreadable as its format) or `missing` (not written).

| Format | `values` |
|---|---|
| `junit` | `tests`, `failures`, `errors`, `skipped`: counts |
| `cobertura` | `linePercent`, `branchPercent`: 0 to 100 |
| `sarif` | `findings`: a count |

## The command line

| Command | Does |
|---|---|
| `fsd` | The project: every atom, its binding, compliance per track. Outside a project, the help. |
| `fsd <atom> [args...]` | Runs an atom, standard or custom. `fsd run <atom>` is the same. |
| `fsd <track>` | Runs a checks track: its compliance first, then its atoms in order, stopping at the first failure. Takes no arguments. The gate is `fsd assurance`, `fsd security` and `fsd documentation`. |
| `fsd report` | Every routine atom; writes `fsd-report.json` and `fsd-report.md` to the project root. |
| `fsd help [name] [--json]` | The standard, one track, or one atom: its contract, and its binding here. With a broken `fsd.toml` it warns and shows the standard alone. `--json` gives an object whose `kind` is `standard`, `track`, `atom` (with its `binding`, `null` outside a project) or `custom`. |
| `fsd --version` | The version of `fsd` and of the standard it ships. |
| `fsd -C DIR …` | Starts the search for `fsd.toml` from `DIR`, which must be a directory. |

`fsd`'s own options come before the command. Everything after an atom's name
belongs to the atom.

| Exit code | Means |
|---|---|
| 0 | compliant, and everything run passed |
| 1 | not compliant, or something run failed |
| 2 | the input was invalid: `fsd.toml`, an unknown atom, or arguments a command cannot take |

## Errors

Every error is a `forktex.error.AppError` with a `code` and `details`.

| Error | Code | Raised when | `details` |
|---|---|---|---|
| `FsdError` | `internal` | the base of all of them | |
| `BindingError` | `validation` | `fsd.toml` is invalid or contradicts the standard | `atom` or `section` or `key`, and `expected` where there is one |
| `InvalidStandardError` | `validation` | a standard does not parse | |
| `ProjectNotFoundError` | `not_found` | there is no `fsd.toml` where one was looked for | `root` or `start` |
| `UnknownAtomError` | `not_found` | a name is neither a track, a standard atom nor a custom one | `atom` |
| `UsageError` | `bad_request` | arguments an atom cannot take, or a track that does not run as a whole | `track`, for a track |
