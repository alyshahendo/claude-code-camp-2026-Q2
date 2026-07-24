# 04 · The API Client (Python)

Python port of the Ruby step 4 API client.

The API Client takes the payload assembled by `PromptBuilder` and sends it to the
API. One HTTP POST, one response. No tool loop yet, this just proves the round
trip works.

## New Files

| File | Description |
|---|---|
| `boukensha/client.py` | Makes the HTTP request and parses the response |

## Updated Files

| File | Change |
|---|---|
| `boukensha/errors.py` | Added `ApiError` for failed HTTP requests |
| `boukensha/config.py` | `PROMPTS_DIR` now resolves one level above the step, matching the Ruby reference |
| `prompts/system.md` | New default system prompt |

## How It Works

```
PromptBuilder
      ↓
Client
      ↓
POST to API endpoint
      ↓
Raw JSON response (dict)
```

## `boukensha.Client`

| Method | Description |
|---|---|
| `call(max_output_tokens=1024)` | POSTs the payload and returns the parsed JSON response |

On any non-2xx response the client raises `boukensha.ApiError`. Transient network
failures and retryable status codes (408, 409, 429, 5xx) are retried up to three
times with exponential backoff before giving up.

## Task Configuration

This step uses the task based configuration from the earlier steps:

```yaml
tasks:
  player:
    provider: anthropic
    model: claude-haiku-4-5
    prompt_override:
      system: true
```

When `prompt_override.system` is true, Boukensha reads
`.boukensha/prompts/player/system.md`. Otherwise it falls back to this step's
shipped `prompts/system.md`.

Each backend validates the configured model at construction time. Unsupported
model names raise `UnsupportedModelError`, and supported models expose backend
owned metadata such as `context_window`, `usage_unit`, and token cost estimates
for later logging steps.

## No Dependencies

`Client` uses Python's standard library `urllib`. No third party HTTP client.
This is intentional: the HTTP call itself is trivial and should be visible, not
hidden behind a library.

SSL is handled automatically. `urllib` enables it for `https` URLs and verifies
against the system certificate store. A local Ollama endpoint uses plain `http`,
so no SSL is needed there.

## What the Response Looks Like

The raw response shape differs between backends. This is what you get back from
`client.call()` before any processing:

### Anthropic
```json
{
  "id": "msg_01XY",
  "type": "message",
  "role": "assistant",
  "content": [
    { "type": "text", "text": "Sure, let me read that file." }
  ],
  "stop_reason": "end_turn",
  "usage": { "input_tokens": 42, "output_tokens": 18 }
}
```

### Ollama
```json
{
  "model": "llama3.2",
  "message": {
    "role": "assistant",
    "content": "Sure, let me read that file."
  },
  "done_reason": "stop",
  "done": true
}
```

When the model wants to call a tool the response looks different. Anthropic uses
`stop_reason: "tool_use"` and adds a `tool_use` block to `content`. Ollama adds a
`tool_calls` array to `message`. Handling those differences is the job of step 5,
the Agent Loop.

## Considerations

**The client raises `ApiError` on failure.** A non-2xx response means something
went wrong (bad API key, malformed payload, server error). Boukensha surfaces
this explicitly rather than returning a confusing `None` or partial response.

**Running the example makes a real API call.** It needs a valid key for the
configured provider (for example `ANTHROPIC_API_KEY`), read from
`.boukensha/.env`.

## Run Example

```bash
./week1_baseline/bin/python/04_api_client
```

Or directly:

```bash
cd week1_baseline/python/04_api_client
uv run python examples/example.py
```
