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

from boukensha import Config  # noqa: E402
from boukensha.tasks import Player  # noqa: E402

config = Config()
player_settings = config.tasks("player")

system_prompt = Player.system_prompt(
    player_settings,
    user_prompts_dir=config.user_prompts_dir,
    default_prompts_dir=Config.PROMPTS_DIR,
)

print("=== Boukensha Step 0: Configuration ===")
print()
print(f"Config dir:     {config.dir}")
print(f"Tasks:          {', '.join(config.tasks().keys())}")
print()
print("-- player task --")
print(f"Provider:       {Player.provider(player_settings)}")
print(f"Model:          {Player.model(player_settings)}")
print(f"Prompt override?{Player.prompt_override(player_settings, 'system')}")
print(f"System prompt:  {(system_prompt or '')[:60]}...")
print()
print(f"MUD host:       {config.mud_host}:{config.mud_port}")
print(f"MUD user:       {config.mud_username}")
print()
print(f"API key set?    {os.environ.get('ANTHROPIC_API_KEY') is not None}")
print()
print(config)
