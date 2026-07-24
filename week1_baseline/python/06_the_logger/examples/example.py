import os
import sys
from pathlib import Path

# Make the package importable when run directly (examples/ is not on sys.path).
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Override the config directory so the example works from the repo root.
# In real usage a user's ~/.boukensha is picked up automatically.
os.environ.setdefault(
    "BOUKENSHA_DIR",
    str(Path(__file__).resolve().parents[4] / ".boukensha"),
)

import boukensha  # noqa: E402,F401  (available for boukensha.enable_debug())
from boukensha import (  # noqa: E402
    Agent,
    Client,
    Config,
    Context,
    Logger,
    PromptBuilder,
    Registry,
    backends,
)
from boukensha.tasks import Player  # noqa: E402

config = Config()
player_settings = config.tasks("player")
system_prompt = Player.system_prompt(
    player_settings,
    user_prompts_dir=config.user_prompts_dir,
    default_prompts_dir=Config.PROMPTS_DIR,
)
base_dir = Path(__file__).resolve().parent.parent

ctx = Context(task=Player, system=system_prompt)
registry = Registry(ctx)

provider = Player.provider(player_settings)
model = Player.model(player_settings)


def build_backend(provider, model):
    if provider == "anthropic":
        return backends.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"], model=model)
    if provider == "openai":
        return backends.OpenAI(api_key=os.environ["OPENAI_API_KEY"], model=model)
    if provider == "gemini":
        return backends.Gemini(api_key=os.environ["GEMINI_API_KEY"], model=model)
    if provider == "ollama":
        return backends.Ollama(model=model)
    if provider == "ollama_cloud":
        return backends.OllamaCloud(api_key=os.environ["OLLAMA_API_KEY"], model=model)
    raise ValueError(f"Unsupported provider for player task: {provider}")


backend = build_backend(provider, model)
builder = PromptBuilder(ctx, backend)
client = Client(builder)

# Writes structured JSONL events to .boukensha/sessions/<session-id>.jsonl.
# Call boukensha.enable_debug() before running to include the full raw API
# response in those lines.
logger = Logger()
agent = Agent(
    context=ctx,
    registry=registry,
    builder=builder,
    client=client,
    logger=logger,
    task_settings=player_settings,
)

registry.tool(
    "read_file",
    description="Read the contents of a file from disk",
    parameters={"path": {"type": "string", "description": "The file path to read"}},
    block=lambda path: Path(base_dir, path).read_text(),
)

registry.tool(
    "list_directory",
    description="List the files in a directory",
    parameters={"path": {"type": "string", "description": "The directory path to list"}},
    block=lambda path: ", ".join(
        entry for entry in os.listdir(Path(base_dir, path)) if not entry.startswith(".")
    ),
)

ctx.add_message(
    "user",
    "Read the README.md file and summarise what this MUD player assistant framework can do.",
)

print("=== BOUKENSHA Step 6: The Logger ===")
print()
print(f"Config: {config}")
print(f"Provider: {provider}")
print(f"Model: {model}")
print(f"Max iterations: {Player.max_iterations(player_settings)}")
print(f"Max output tokens: {Player.max_output_tokens(player_settings)}")
print()

result = agent.run()

print()
print("=== FINAL RESPONSE ===")
print(result)
