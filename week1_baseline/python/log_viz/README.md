# Log Viz (Python)

Python port of the Ruby Sinatra log viewer. A small Flask app that turns
`.boukensha/sessions/*.jsonl` logs (written by `boukensha.Logger`) into a
human-readable transcript in the browser.

## What it does

- **`/`** — lists every session log (start time, session id, logged task,
  provider/model mix, iteration count, token totals, and cost).
- **`/sessions/<id>`** — renders one session as a chat-style transcript:
  - the user's task
  - assistant replies, with input/output token counts, provider/model, and
    per-call cost when the logger recorded it
  - cost and token breakdowns grouped by task, provider, and model
  - each tool call and its result, grouped by agent iteration
  - raw MUD output (including ANSI color codes) is converted to colored HTML

It only reads the `.jsonl` files — nothing is written back.

## Run it

```bash
./bin/log_viz
```

Or directly:

```bash
uv run python -m log_viz
```

Then open <http://localhost:4567>.

## Configuration

| Env var | Default | Purpose |
|---|---|---|
| `LOG_VIZ_SESSIONS_DIR` | `<repo root>/.boukensha/sessions` | Directory of `.jsonl` session logs to read |
| `PORT` | `4567` | Port to listen on |
| `BIND` | `localhost` | Address to bind to |

## How it works

- `log_viz/session.py` — reads a `.jsonl` file and turns the raw
  `session_start` / `iteration` / `prompt` / `response` / `tool_call` /
  `tool_result` / `turn_end` events into an ordered list of transcript entries
  (`user`, `assistant`, `tool`). Response events are the source of truth for
  task/provider/model/cost, so one session can mix models.
- `log_viz/ansi.py` — converts ANSI SGR escape codes in tool results into
  `<span>` elements styled via `static/style.css`.
- `log_viz/app.py` — the Flask app and Jinja view helpers.
- `log_viz/templates/` — Jinja templates for the session list and transcript
  pages (the Ruby ERB views).

## Notes on the port

The Ruby app uses Sinatra + ERB; this port uses Flask + Jinja2. Jinja
auto-escapes by default, so the view helpers that emit HTML (`progress_bar`,
`ctx_chip`, `sparkline`, `ansi_html`, `text_html`, `fmt_cost`) return
`markupsafe.Markup` to match the un-escaped ERB behaviour. The transcript
supports event types (`compaction`, `reasoning`, `plan`, `turn`) that the
current logger does not emit yet; they are carried over from the Ruby source so
the viewer keeps working as the logger grows.
