# 03 · The Prompt Builder (Python)

Python port of the Ruby step 3 prompt builder.

Because LLM access, cost and quality are constantly changing, we want to be able
to switch between multiple LLMs that will drive the agent loop. The Prompt
Builder serializes `Context` into the exact format each API expects, delegating
to whichever backend you pass in.

`PromptBuilder` does not call the API, we are simply preparing the format for API
calls.

Configuration is task based, carried forward from the registry step. The
`player` task owns its provider, model, and prompt override settings, and the
context records the task that the prompt is being built for.

## New Files

| File | Description |
|---|---|
| `boukensha/prompt_builder.py` | Delegates serialization to the active backend |
| `boukensha/backends/base.py` | Shared backend contract for model validation and model metadata |
| `boukensha/backends/anthropic.py` | Serializes context into the Anthropic API format |
| `boukensha/backends/ollama.py` | Serializes context into the Ollama API format |
| `boukensha/backends/ollama_cloud.py` | Serializes context into the Ollama Cloud API format |
| `boukensha/backends/openai.py` | Serializes context into the OpenAI Chat Completions format |
| `boukensha/backends/gemini.py` | Serializes context into the Gemini `generateContent` format |

## How It Works

```
Context (Python objects)
        ↓
PromptBuilder
        ↓
Backend (Anthropic, OpenAI, Gemini, or Ollama)
        ↓
API Payload (plain dicts and lists)
        ↓
POST to API
```

## `boukensha.PromptBuilder`

| Method | Description |
|---|---|
| `to_messages()` | Delegates message serialization to the backend |
| `to_tools()` | Delegates tool serialization to the backend |
| `to_api_payload(max_output_tokens=1024)` | Assembles the complete payload ready to POST |
| `headers()` | Returns the correct headers for the backend |
| `url()` | Returns the correct endpoint URL for the backend |

## Backends

Each API has its own conventions for how data is expected. Anthropic and Gemini
are the most alike (system prompt as a top level field), while OpenAI and Ollama
share the same `function` wrapped tool schema.

Backends also own their supported model table. A backend refuses to initialize
with an unknown model, so `settings.yaml` cannot silently select an unsupported
or misspelled model. Each model entry carries:

| Key | Meaning |
|---|---|
| `context_window` | The model's known token context window |
| `cost_per_million["input"]` | USD input token price per million tokens, when known |
| `cost_per_million["output"]` | USD output token price per million tokens, when known |
| `usage_unit` | `"tokens"`, `"local_compute"`, or `"ollama_cloud_usage"` |
| `usage_level` | Ollama Cloud usage tier, when applicable |

Backend instances expose `context_window`, `input_token_cost_per_million`,
`output_token_cost_per_million`, `usage_unit`, `usage_level`, and
`estimate_cost(input_tokens, output_tokens)`. For local Ollama models, token API
cost is `0.0`. For Ollama Cloud, public pricing is plan/usage based rather than
token based, so `estimate_cost` returns `None`.

The prices in this step are static tutorial data, current as of June 16, 2026,
and should be reviewed whenever the selected model set changes.

An unknown model raises `boukensha.UnsupportedModelError`.

### `boukensha.backends.Anthropic`

Talks to `https://api.anthropic.com/v1/messages`. Requires an `ANTHROPIC_API_KEY`.
Supported models are listed in `Anthropic.MODELS`.

### `boukensha.backends.Ollama`

Talks to `http://localhost:11434/api/chat`. Requires `ollama serve` running
locally. No API key needed. Supported models are listed in `Ollama.MODELS`.

### `boukensha.backends.OllamaCloud`

Talks to `https://ollama.com/api/chat`. Requires an `OLLAMA_API_KEY`. Supported
models are listed in `OllamaCloud.MODELS`.

### `boukensha.backends.OpenAI`

Talks to `https://api.openai.com/v1/chat/completions`. Requires an
`OPENAI_API_KEY`. Supported models are listed in `OpenAI.MODELS`.

### `boukensha.backends.Gemini`

Talks to `https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent`.
Requires a `GEMINI_API_KEY`. Supported models are listed in `Gemini.MODELS`.

### System Prompt

Anthropic and Gemini send the system prompt as a top level field, separate from
the messages array. Ollama and OpenAI put it inside the messages array as a
`role: system` message.

### Tool Results

Anthropic wraps tool results in a user message. Ollama and OpenAI use their own
`role: tool` message type (with slightly different identifier fields). Gemini
wraps results in a `functionResponse` part on a `user` message.

### Message Roles

Anthropic, Ollama, and OpenAI all use `assistant` for the model's turn. Gemini
calls it `model`.

## Considerations

**The conversation is stateless.** The model has no memory between turns. Every
API call includes the entire history from the beginning. BOUKENSHA is
responsible for carrying that state.

**Tool results are user messages on Anthropic.** This feels counterintuitive,
the result came from BOUKENSHA, not the human, but it reflects how the Anthropic
API models the conversation. Ollama, OpenAI, and Gemini all handle this with
dedicated message/part types instead.

**The agent only sees schemas.** The `description` field on each tool is the only
thing the agent uses to decide which tool to call. The actual block never leaves
BOUKENSHA.

## Run Example

```bash
./week1_baseline/bin/python/03_prompt_builder
```

Or directly:

```bash
cd week1_baseline/python/03_prompt_builder
uv run python examples/example.py
```
