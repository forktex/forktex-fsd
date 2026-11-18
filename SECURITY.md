# Security Policy

## Reporting a vulnerability

Email **info@forktex.com** with details and, where possible, a reproduction. Please do
not open a public issue for an unfixed vulnerability.

## Supported versions

| Version | Supported |
| --- | --- |
| 1.x | ✅ |

## Scope

`forktex-fsd` reads a repository's `fsd.toml` and, when asked through `fsd <atom>`,
`fsd <track>` or `fsd report`, executes the commands that file names.

- **The compliance check executes nothing.** `Project.check()` reads `fsd.toml` and tests
  whether bound files exist; it is safe on an untrusted repository. `fsd <track>`
  runs the check and then the repository's own commands.
- **Running an atom, a track or a report executes the repository's own commands**, with the caller's privileges and
  in the repository's directory. A string binding runs through the platform shell.
  Running an atom, a track or `fsd report` on a repository you do not trust is running that repository's
  code — exactly as `make` or `npm run` would be.
- **Atoms beyond the workspace** (`install`, `publish`, `deploy`, `rollback`) belong to no track that runs
  as a whole, and a report leaves them out; they run only when named on their own.
- **`fsd report` runs every routine atom**, including `setup` and any custom
  atom of a checks track, and reads the result files the bindings name from
  the repository's own tree.
- **Arguments** passed after an atom's name are quoted for the platform shell.
  Under Windows `cmd`, a `%` in an argument still expands an environment
  variable; `cmd` has no escape for it inside a quoted argument. A binding that wraps
  `{args}` in its own quotes (`"{args}"`) undoes the quoting, and the shell
  expands what is inside: write `{args}` bare.
- **File and result paths** must stay inside the repository; a symbolic link
  that resolves outside it is treated as missing, never read.
