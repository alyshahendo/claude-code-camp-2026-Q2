# 05 · The Agent Loop (Python)

Python port of the Ruby step 5 agent loop.

The Agent Loop is the heart of Boukensha. Everything built before this (the
structs, the registry, the prompt builder, the client) was setup. The loop is
where the agent actually does work.

## New Files

| File | Description |
|---|---|
| `boukensha/agent.py` | The agent loop: sends requests, dispatches tools, and knows when to stop |

## Updated Files

| File | Change |
|---|---|
| `boukensha/errors.py` | Added `LoopError` for runaway agents |
| `boukensha/prompt_builder.py` | Added `parse_response`, delegating to the backend; `to_api_payload` takes a `tools` override |
| `boukensha/client.py` | `call` takes a `tools` override (used by the tools-disabled wind-down call) |
| `boukensha/tasks/base.py` | Added `max_iterations` and `max_output_tokens` task settings |
| `boukensha/backends/*.py` | Added `parse_response`; the non-Anthropic backends rebuild assistant messages from normalized content |

## How It Works

```
send messages to API
        ↓
stop_reason == "tool_use"?
    yes → extract tool calls
        → dispatch each tool via Registry
        → inject results as tool_result messages
        → go back to top
    no  → return final text response
```

## `boukensha.Agent`

| Method | Description |
|---|---|
| `run()` | Starts the loop and returns the final text response when the agent is done |

## Every Backend Speaks the Same Normalized Shape

Five providers means five different response formats. Anthropic nests tool calls
inside `content`, Ollama puts them in `message.tool_calls`, OpenAI nests them
under `choices[0].message.tool_calls`, and Gemini calls them `functionCall`
parts. Rather than teach the agent loop about each of these, every backend
implements `parse_response`, converting its raw response into one common shape:

```python
{
    "stop_reason": "tool_use" | "end_turn",
    "content": [
        {"type": "text", "text": "..."},
        {"type": "tool_use", "id": "...", "name": "...", "input": {...}},
    ],
}
```

`Agent` only ever sees this shape. It calls `builder.parse_response(response)`,
which delegates to the backend, and never inspects a raw provider response.
That is what keeps `agent.py` down to a single
`if parsed["stop_reason"] == "tool_use"` branch.

The conversion also runs in reverse. When the conversation history is replayed
on the next request, Ollama, Ollama Cloud, OpenAI, and Gemini each rebuild a
provider-specific assistant message from the normalized `content` blocks via a
private `_assistant_message` (or `_assistant_parts`) method, the inverse of
`parse_response`. Anthropic's `content` array doubles as both the normalized
shape and the wire format, so it needs no extra conversion.

**Tool call IDs are not universal.** Anthropic and OpenAI assign every tool call
a unique `id`, echoed back in the `tool_result`. Ollama, Ollama Cloud, and Gemini
do not assign call ids at all; those backends reuse the tool's `name` as its `id`
and match the `tool_result` back to the call by name.

## Task Configuration

This step uses the task based configuration from the earlier steps:

```yaml
tasks:
  player:
    provider: anthropic
    model: claude-haiku-4-5
    prompt_override:
      system: true
    max_iterations: 25
    max_output_tokens: 1024
```

`max_iterations` controls model round-trips per turn before wind-down, and
`max_output_tokens` is passed to each model reply. Both fall back to defaults
(25 and 1024) when absent.

| Provider | Backend | Requires |
|---|---|---|
| `anthropic` | `backends.Anthropic` | `ANTHROPIC_API_KEY` |
| `openai` | `backends.OpenAI` | `OPENAI_API_KEY` |
| `gemini` | `backends.Gemini` | `GEMINI_API_KEY` |
| `ollama` | `backends.Ollama` | a local Ollama server (`host` defaults to `http://localhost:11434`) |
| `ollama_cloud` | `backends.OllamaCloud` | `OLLAMA_API_KEY` |

## What the Loop Looks Like

Running the example produces output like this:

```
=== BOUKENSHA Step 5: Agent Loop ===

[iteration 1/25]
  tool call → list_directory({'path': '.'})
  tool result → README.md, boukensha, examples, prompts, pyproject.toml
...

=== FINAL RESPONSE ===
Here is what this framework can do: ...
```

## Considerations

**The assistant message must be stored before the tool result.** The Anthropic
API requires the assistant's tool_use block to appear in the message history
before its corresponding tool_result. `Agent` handles this in
`_handle_tool_calls`: get the order wrong and the API rejects the request.

**The model can call multiple tools in one turn.** The loop iterates over all
tool_use blocks in a single response before making the next API call.

**`MAX_ITERATIONS` is a turn ceiling.** A poorly prompted agent can loop forever
if the model keeps calling tools. Boukensha stops starting new work after 25
iterations by default and makes one short wrap-up call with tools disabled. This
keeps the turn bounded while still returning a useful final response.

**The agent has no way to stop itself.** The model signals it is done via
`stop_reason: "end_turn"`. Boukensha watches for that signal and exits the loop.
The agent never decides unilaterally to stop.

## Run Example

```bash
./week1_baseline/bin/python/05_agent_loop
```

Or directly:

```bash
cd week1_baseline/python/05_agent_loop
uv run python examples/example.py
```
