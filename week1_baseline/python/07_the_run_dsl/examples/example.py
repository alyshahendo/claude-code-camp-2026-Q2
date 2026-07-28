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

import boukensha  # noqa: E402

# Config is loaded automatically inside boukensha.run — system prompt, model,
# and API key all come from ~/.boukensha (or BOUKENSHA_DIR) by default. You can
# still override any of them as keyword arguments if you want.

print("=== BOUKENSHA Step 7: The Boukensha.run DSL ===")
print()
print(f"Config: {boukensha.config()}")
print()

base_dir = Path(__file__).resolve().parent.parent


# The block receives a RunDSL. Ruby uses instance_eval so `self` becomes the
# RunDSL and `tool` can be called bare; Python passes the DSL in explicitly.
def register_tools(dsl):
    dsl.tool(
        "read_file",
        description="Read the contents of a file from disk",
        parameters={"path": {"type": "string", "description": "The file path to read"}},
        block=lambda path: Path(base_dir, path).read_text(),
    )
    dsl.tool(
        "list_directory",
        description="List the files in a directory",
        parameters={"path": {"type": "string", "description": "The directory path to list"}},
        block=lambda path: ", ".join(
            entry for entry in os.listdir(Path(base_dir, path)) if not entry.startswith(".")
        ),
    )


result = boukensha.run(
    task="Read the README.md file and summarise what this MUD player assistant framework can do.",
    block=register_tools,
)

print()
print("=== FINAL RESPONSE ===")
print(result)
