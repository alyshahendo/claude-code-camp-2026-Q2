# 09 · The Global Executable (Python)

Python port of the Ruby step 9 global executable.

Package Boukensha so the `boukensha` command works from anywhere on your machine.

## What this step adds

- `pyproject.toml` `[project.scripts]` — declares the `boukensha` console script,
  the Python analog of the Ruby gem's `bin/boukensha` executable.
- `boukensha_loader.py` — resolves *which step folder* to load from, then boots
  the REPL. It lives outside the `boukensha` package because its job is to decide
  which `boukensha` to import.
- The `boukensha/` package — step 8's lib, bundled as the default.

## Updated Files

| File | Change |
|---|---|
| `boukensha/version.py` | Bumped to `0.9.0` |
| `boukensha/repl.py` | Simplified banner: separate `config` / `provider` / `model` lines |
| `boukensha/client.py` | Dropped the special-case `401` message |
| `boukensha/config.py` | Config dir resolution is back to `BOUKENSHA_DIR` or `~/.boukensha` (no cwd lookup) |

The version is a single source of truth: `pyproject.toml` reads it from
`boukensha/version.py` (the analog of the gemspec's `spec.version = Boukensha::VERSION`).

## Install

From this folder:

```bash
# global, isolated (recommended) — needs uv or pipx
uv tool install .
# or: pipx install .

boukensha        # now on your PATH, works from any directory
```

`uv tool install` / `pipx install` put the `boukensha` command on your PATH in an
isolated environment. To try it without a global install, run it in the project
venv:

```bash
uv run boukensha
```

## Switching steps with BOUKENSHA_PATH

The loader resolves in this order:

| Priority | Source | Example |
|----------|--------|---------|
| 1 | `BOUKENSHA_PATH` env var | `BOUKENSHA_PATH=~/repos/.../python/08_the_repl_loop boukensha` |
| 2 | `~/.boukensharc` file | `echo ~/repos/.../python/08_the_repl_loop > ~/.boukensharc` |
| 3 | Bundled default | just run `boukensha` |

`BOUKENSHA_PATH` must point to a step folder that contains `boukensha/__init__.py`.
Pointing it at a pre-REPL step prints a friendly message instead of crashing.

## Config

The command needs a config dir (settings + API key), resolved separately by
`Config`: `BOUKENSHA_DIR` env var, else `~/.boukensha`. Set `BOUKENSHA_DIR` (or
export it in your shell profile) to use a specific `.boukensha`:

```bash
BOUKENSHA_DIR=~/repos/claude-code-camp-2026-Q2/.boukensha boukensha
```

## Debug mode

```bash
BOUKENSHA_DEBUG=1 boukensha
# => [boukensha] loading from: /path/to/step
```

## The key idea

The install is just a **wrapper and a default**. All the teaching material stays
in the numbered step folders exactly as it was. The console script doesn't copy
or symlink anything — it just knows where to look.
