# 00 · Configuration (Python)

Python port of the Ruby step 0 configuration library.

We want to manage all configuration from an external file, e.g.
`~/.boukensha/settings.yaml`, through a dedicated `Config` class
(`boukensha.Config`). As each iteration adds configuration we update the schema
and class. Defaults may be hardcoded, but configurable values must not be.

Configuration is organised by **task**: a role in the agentic loop bound to its
own LLM. week1_baseline only drives a single `player` task (the main loop), but a
more advanced loop will assign different LLMs to different tasks.

## Design considerations

Prefer the standard library. The only external dependencies are `pyyaml` (Python
has no standard library YAML parser) and `python-dotenv` (to load `.env` files).

## Layout

| File | Purpose |
|------|---------|
| `boukensha/config.py` | `Config` class |
| `boukensha/tasks/base.py` | abstract `Base` (provider/model + prompt resolution) |
| `boukensha/tasks/player.py` | concrete `Player` (the main loop) |
| `boukensha/__init__.py` | top level exports |
| `prompts/system.md` | default system prompt shipped with the library |
| `examples/example.py` | runnable smoke test |

## Config directory resolution

The class looks for a `.boukensha/` directory in this order:

1. **`BOUKENSHA_DIR` env var** — point it at any directory you like.
2. **`~/.boukensha`** — the default location for a real install.

## Config directory structure

```
.boukensha/
  .env                 # credentials, e.g. LLM API keys (never committed)
  settings.yaml        # all non secret settings
  prompts/
    <task>/
      system.md        # per task override of the default system prompt (optional)
```

## Tasks

`boukensha.tasks.Base` is abstract and stateless. All behaviour is expressed as
class methods that accept a `settings` dict; no instances are created. Concrete
subclasses override `task_name`. For now only `Player` exists.

`Config.tasks()` returns the raw mapping from `settings.yaml` under `tasks:`. Pass
a name to look up one task's settings dict, then pass it to the stateless class:

```python
from boukensha import Config
from boukensha.tasks import Player

config = Config()
Player.provider(config.tasks("player"))
Player.system_prompt(
    config.tasks("player"),
    user_prompts_dir=config.user_prompts_dir,
    default_prompts_dir=Config.PROMPTS_DIR,
)
```

## System prompt resolution

Per task, `system_prompt` resolves in this order:

1. **`.boukensha/prompts/<task>/system.md`** — used when the task's
   `prompt_override.system` is `true` and the file exists.
2. **`prompts/system.md`** — the default system prompt shipped with the library.

## Configuration schema

- `tasks`: a map of task name to task config (provider, model, prompt_override).
- `tasks.<name>.prompt_override.system`: when `true`, the task's
  `.boukensha/prompts/<name>/system.md` overrides the default system prompt.
- `mud`: MUD connection information for the main player.

```yaml
tasks:
  player:
    provider: anthropic
    model: claude-haiku-4-5
    prompt_override:
      system: true
mud:
  host: localhost
  port: 4000
  username: dummy
  password: helloworld
```

## Run example

```bash
./week1_baseline/bin/python/00_config
```

Or directly:

```bash
cd week1_baseline/python/00_config
uv run python examples/example.py
```
