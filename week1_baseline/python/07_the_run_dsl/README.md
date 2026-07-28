# 07 · The run DSL (Python)

Python port of the Ruby step 7 run DSL.

## What this step adds

A single top-level entry point: `boukensha.run`.

Every previous step required you to manually create and wire together a
`Context`, `Registry`, backend, `PromptBuilder`, `Client`, `Logger`, and
`Agent`. This step hides all of that behind one function call and a block.

## New Files

| File | Description |
|---|---|
| `boukensha/run_dsl.py` | `RunDSL`, the tiny host object handed to a `run` block |

## Updated Files

| File | Change |
|---|---|
| `boukensha/__init__.py` | Added the `run()` entry point and re-exported `LoopError` |
| `boukensha/errors.py` | Restored `LoopError` |
| `boukensha/config.py` | Restored the MUD connection accessors |
| `boukensha/logger.py` | Added `turn()` and a `subscribe()` fan-out on every logged event |

## `boukensha.RunDSL`

A tiny host object exposing only `tool`. In Ruby, `run` does
`instance_eval(&block)` so `self` inside the block becomes the `RunDSL` and
`tool` can be called bare. Python has no `instance_eval`, so `run` calls the
block with the `RunDSL` instance as its argument instead.

## `boukensha.run`

Accepts keyword arguments that describe *what* to do; all plumbing is handled
internally.

| Option | Default | Description |
|---|---|---|
| `task` | *(required)* | The user message handed to the agent |
| `system` | task's system prompt | System prompt |
| `model` | task's configured model | Model name |
| `backend` | task's configured provider | `"anthropic"`, `"openai"`, `"gemini"`, `"ollama"`, or `"ollama_cloud"` |
| `api_key` | matching `*_API_KEY` env var | API key for the chosen backend (not needed for `"ollama"`) |
| `ollama_host` | `"http://localhost:11434"` | Ollama base URL |
| `log` | `None` | Optional JSONL path override; defaults to `.boukensha/sessions/<session-id>.jsonl` |
| `max_output_tokens` | task's configured value | Per-reply output cap |
| `block` | `None` | A callable that receives a `RunDSL` to register tools |

## Before and after

**Manual plumbing (step 5):**

```python
ctx = Context(task=Player, system="You are a MUD player assistant.")
registry = Registry(ctx)
backend = backends.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"], model="claude-haiku-4-5")
builder = PromptBuilder(ctx, backend)
client = Client(builder)
logger = Logger()
agent = Agent(context=ctx, registry=registry, builder=builder, client=client, logger=logger)

registry.tool("read_file", description="Read a file",
              parameters={"path": {"type": "string"}}, block=lambda path: open(path).read())

ctx.add_message("user", "Read boukensha/__init__.py")
agent.run()
```

**Just describe what you want (step 7):**

```python
def define(dsl):
    dsl.tool(
        "read_file",
        description="Read a file",
        parameters={"path": {"type": "string", "description": "File path"}},
        block=lambda path: open(path).read(),
    )

boukensha.run(task="Read boukensha/__init__.py", block=define)
```

## Run Example

```bash
./week1_baseline/bin/python/07_the_run_dsl
```

Or directly:

```bash
cd week1_baseline/python/07_the_run_dsl
uv run python examples/example.py
```

The agent loop is quiet; the logger writes a session JSONL file under
`.boukensha/sessions`. View it with the log viewer in `python/log_viz`.
