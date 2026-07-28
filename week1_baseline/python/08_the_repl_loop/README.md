# 08 · The REPL Loop (Python)

Python port of the Ruby step 8 REPL loop.

## What this step adds

| | Step 7 | Step 8 |
|---|---|---|
| Entry point | `boukensha.run(task=…)` | `boukensha.repl(…)` |
| Turns | one | many |
| History | discarded | accumulates across turns |
| User interaction | none | stdin prompt |

## New Files

| File | Description |
|---|---|
| `boukensha/repl.py` | `Repl`, the interactive session loop |
| `boukensha/version.py` | `VERSION` string shown in the REPL banner |

## Updated Files

| File | Change |
|---|---|
| `boukensha/__init__.py` | Added the `repl()` entry point (shares wiring with `run()`) |
| `boukensha/agent.py` | Persists the final assistant reply to the context so later turns see it |
| `boukensha/context.py` | Added `clear_messages()` for the REPL `/clear` command |
| `boukensha/client.py` | Raises a clear `ApiError` on a `401` (bad API key) |
| `boukensha/config.py` | Config dir resolution now also checks `./.boukensha` in the working directory |

## `boukensha.Repl`

The interactive session loop. Built-in commands (not sent to the agent):

| Command | Effect |
|---|---|
| `/quiet` | Suppress logging output |
| `/loud` | Re-enable logging output |
| `/clear` | Wipe conversation history (tools stay registered) |
| `/help` | Print the command list |
| `/exit` / `/quit` | Leave the REPL |
| Ctrl-D | EOF — leave the REPL |
| Ctrl-C | Interrupt — leave the REPL gracefully |

## `boukensha.repl`

Same signature as `boukensha.run`, minus `task`. Register tools in the block;
then the REPL loop takes over reading tasks from stdin.

```python
def define(dsl):
    dsl.tool(
        "read_file",
        description="Read a file from disk",
        parameters={"path": {"type": "string", "description": "File path"}},
        block=lambda path: open(path).read(),
    )

boukensha.repl(model="claude-haiku-4-5", block=define)
```

## Why the agent now persists its reply

Before this step, the agent returned the final text without adding it to the
context. That was fine for one-shot runs (the context is thrown away anyway), but
a REPL needs the full transcript so subsequent turns see the prior exchange. The
agent now appends the final assistant message to the context in every
termination path before returning it.

## Run Example

```bash
./week1_baseline/bin/python/08_the_repl_loop
```

Or directly:

```bash
cd week1_baseline/python/08_the_repl_loop
uv run python examples/example.py
```

Then type tasks at the `boukensha>` prompt. The last question in a session can
reference earlier ones because history accumulates across turns. Each turn writes
a session JSONL file under `.boukensha/sessions` (view it with `python/log_viz`).
