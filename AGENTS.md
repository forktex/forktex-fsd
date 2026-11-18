# AGENTS.md

`forktex-fsd` is a general-purpose software compliance standard and the small
library + CLI that checks it. It must stay technology-agnostic and free of any
ForkTex-specific assumption: it judges compliance per track, never a product's
stage or maturity.

- **The standard is data**: `src/forktex_fsd/standard.toml`. Changing an atom, a
  contract or a strength is a change to the standard — bump its `version` and
  record it in `CHANGELOG.md`. Contracts never name a tool.
- **Built on `forktex`**: errors subclass `forktex.error.AppError`, every model is
  a `forktex.types` value object (pydantic — never a dataclass), the report is a
  wire object, the library logs and never prints.
- **Layout and direction**: `standard` → `binding` | `results` → `check` | `run`
  → `report` → `project` → `_render` → `_cli`, one way only; `fsd lint` enforces
  it. `Project` is the one entry point; `_cli` imports only the package's public
  names and `_render`. `forktex_fsd.__all__` is the public surface, pinned by
  `tests/contract/test_surface.py`. Architecture and decisions: `docs/development.md`.
- `check` must never execute a command. Only checks tracks run as a whole, and
  they may hold only read-only and local atoms; a report runs nothing else.
- There is no Makefile: `fsd.toml` is the only place a command lives.
  `poetry run fsd assurance`, `fsd security` and `fsd documentation` are the gate and `poetry run fsd build` makes the
  artifact; `poetry run fsd tidy` fixes formatting and headers; bare
  `poetry run fsd` shows every atom and its binding. Line and branch
  coverage are held at 100: every branch here is a rule of the standard, so every
  branch has a test. Tests run real subprocesses, not mocks: a consumer's scenario
  goes in `tests/usage/`, a rule in `tests/contract/`. `fsd assurance` includes the
  custom atom `platforms` (`tests/platforms/`, testcontainers), so it needs Docker;
  `fsd test` alone does not.
- Publishing is manual: a person runs `poetry run fsd publish`.
