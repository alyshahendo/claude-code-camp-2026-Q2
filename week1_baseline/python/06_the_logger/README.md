# 06 · The Logger (Python)

Python port of the Ruby step 6 logger.

`boukensha.Logger` records each agent run as structured JSON Lines. It is a file
logger, not user-facing display output. In this step the agent loop stops
printing to stdout and routes every phase of the turn through the logger instead.

## New Files

| File | Description |
|---|---|
| `boukensha/logger.py` | The session logger: one JSONL file per run |

## Updated Files

| File | Change |
|---|---|
| `boukensha/__init__.py` | Package-level singleton state: `config()`, `enable_debug()`/`is_debug()`, `enable_quiet()`/`disable_quiet()`/`is_quiet()` |
| `boukensha/agent.py` | Takes a `logger`; logs each phase instead of printing; tool dispatch errors are caught and logged |
| `boukensha/prompt_builder.py` | Exposes `backend` (so the agent can log provider/model/cost) |
| `boukensha/errors.py` | Removed the unused `LoopError` |
| `boukensha/config.py` | Removed the unused MUD connection accessors |

## Session Logs

Each `Logger` instance creates a session id and writes one log file for that
session:

```text
.boukensha/sessions/<session-id>.jsonl
```

Every line is a complete JSON object with `session_id`, `at`, and `phase`
fields, plus phase-specific data. This keeps logs grep/tail friendly and machine
readable.

```json
{"phase":"session_start","session_id":"20260528T143011Z-a1b2c3d4","at":"2026-05-28T10:30:11-04:00"}
{"phase":"iteration","n":1,"max":25,"session_id":"20260528T143011Z-a1b2c3d4","at":"2026-05-28T10:30:11-04:00"}
```

Model response lines include the active task, provider, model, normalized token
counts, and estimated USD cost when the backend has token pricing data:

```json
{"phase":"response","task":"player","provider":"anthropic","model":"claude-haiku-4-5","input_tokens":1000,"output_tokens":100,"cost_usd":0.0015}
```

## Logger API

A plain object with one method per phase:

| Method | Phase | Logs |
|---|---|---|
| `iteration(n, max)` | `iteration` | loop counter |
| `limit_reached(kind, n, max)` | `limit_reached` | which ceiling was hit |
| `prompt(messages, tools)` | `prompt` | messages and tools sent to the model |
| `tool_call(name, args)` | `tool_call` | tool name and arguments |
| `tool_result(name, result, ok, error)` | `tool_result` | tool result (or error) |
| `response(text, usage, stop_reason, task, backend)` | `response` | response text, token usage, task/provider/model, estimated cost |
| `turn_end(reason, iterations, tokens)` | `turn_end` | how and when the turn ended |
| `raw(data)` | `raw` | raw provider response when debug is enabled |

## Task Configuration

Step 6 uses the task based settings shape:

```yaml
tasks:
  player:
    provider: anthropic
    model: claude-haiku-4-5
    prompt_override:
      system: true
```

When `prompt_override.system` is true, the player task reads
`.boukensha/prompts/player/system.md`. Otherwise it falls back to this step's
shipped `prompts/system.md`.

Default usage:

```python
logger = Logger()
agent = Agent(context=ctx, registry=registry,
              builder=builder, client=client,
              logger=logger)
```

You can also provide a session id or override the destination directory:

```python
Logger(session_id="manual-session")
Logger(dir="/tmp/boukensha-sessions")
```

For compatibility, `log` still accepts an explicit file path, but normal
iteration usage should write under `.boukensha/sessions`.

## Debug Events

Call `boukensha.enable_debug()` before running the agent to include raw provider
responses in the log (the Python equivalent of Ruby's `Boukensha.debug!`):

```python
import boukensha
boukensha.enable_debug()
```

## Run Example

```bash
./week1_baseline/bin/python/06_the_logger
```

Or directly:

```bash
cd week1_baseline/python/06_the_logger
uv run python examples/example.py
```

The loop no longer prints per-iteration lines; watch the run in the JSONL file
instead:

```bash
tail -f .boukensha/sessions/*.jsonl
```
