import json
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

from boukensha import Config, Context, PromptBuilder, Registry, backends  # noqa: E402
from boukensha.tasks import Player  # noqa: E402

config = Config()
player_settings = config.tasks("player")
system_prompt = Player.system_prompt(
    player_settings,
    user_prompts_dir=config.user_prompts_dir,
    default_prompts_dir=Config.PROMPTS_DIR,
)

ctx = Context(task=Player, system=system_prompt)
registry = Registry(ctx)

registry.tool(
    "look",
    description="Look around the current room for details",
    parameters={},
    block=lambda: "A damp stone corridor stretches north. Torches flicker on the walls.",
)

registry.tool(
    "move",
    description="Move the player in a direction (north, south, east, west, up, down)",
    parameters={"direction": {"type": "string", "description": "The direction to move"}},
    block=lambda direction: f"You move {direction} into a torch-lit corridor.",
)

ctx.add_message("user", "I just arrived in the dungeon. What's around me, and can you move north?")
ctx.add_message("assistant", "Let me take a look around first.")
ctx.add_message(
    "tool_result",
    "A damp stone corridor stretches north. Torches flicker on the walls.",
    tool_use_id="toolu_01X",
)

print("=== BOUKENSHA Step 3: Prompt Builder ===")
provider = Player.provider(player_settings)
model = Player.model(player_settings)


def build_backend(provider, model):
    if provider == "anthropic":
        return backends.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"], model=model)
    if provider == "ollama":
        return backends.Ollama(model=model)
    if provider == "ollama_cloud":
        return backends.OllamaCloud(api_key=os.environ["OLLAMA_API_KEY"], model=model)
    if provider == "openai":
        return backends.OpenAI(api_key=os.environ["OPENAI_API_KEY"], model=model)
    if provider == "gemini":
        return backends.Gemini(api_key=os.environ["GEMINI_API_KEY"], model=model)
    raise ValueError(f"Unsupported provider for player task: {provider}")


backend = build_backend(provider, model)
builder = PromptBuilder(ctx, backend)

print()
print(f"Config: {config}")
print(f"Provider: {provider}")
print(f"Model: {model}")
print(json.dumps(builder.to_api_payload(), indent=2))
