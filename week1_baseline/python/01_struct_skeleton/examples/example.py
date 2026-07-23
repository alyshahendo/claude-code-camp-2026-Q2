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

from boukensha import Config, Context, Tool  # noqa: E402
from boukensha.tasks import Player  # noqa: E402

config = Config()
player_settings = config.tasks("player")
system_prompt = Player.system_prompt(
    player_settings,
    user_prompts_dir=config.user_prompts_dir,
    default_prompts_dir=Config.PROMPTS_DIR,
)

ctx = Context(task=Player, system=system_prompt)

ctx.register_tool(
    Tool(
        "move",
        "Move the player in a direction (north, south, east, west, up, down)",
        {"direction": {"type": "string", "description": "The direction to move"}},
        lambda direction: f"You move {direction} into a torch-lit corridor.",
    )
)

ctx.add_message("user", "Explore north and tell me what you find.")
ctx.add_message("assistant", "Sure, let me head north and take a look.")

print("=== Boukensha Step 1: Struct Skeleton ===")
print()
print(f"Config:   {config}")
print(f"Context:  {ctx}")
print(f"Tool:     {ctx.tools['move']}")
print("Messages:")
for m in ctx.messages:
    print(f"  {m}")
