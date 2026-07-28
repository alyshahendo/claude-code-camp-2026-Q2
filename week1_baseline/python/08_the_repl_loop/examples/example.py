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

# Config is loaded automatically inside boukensha.repl — system prompt, model,
# and API key all come from ~/.boukensha (or BOUKENSHA_DIR) by default.

print(f"Config: {boukensha.config()}")
print()

# The base directory tools will operate relative to — the step 7 folder makes
# a good playground since it already has source files to read.
base_dir = Path(__file__).resolve().parents[2] / "07_the_run_dsl"


def register_tools(dsl):
    dsl.tool(
        "read_file",
        description="Read the contents of a file from disk",
        parameters={
            "path": {"type": "string", "description": "File path (relative to the working directory)"}
        },
        block=lambda path: Path(base_dir, path).read_text(),
    )
    dsl.tool(
        "list_directory",
        description="List the files in a directory",
        parameters={
            "path": {
                "type": "string",
                "description": "Directory path (relative to the working directory, or '.' for root)",
            }
        },
        block=lambda path: ", ".join(
            sorted(entry for entry in os.listdir(Path(base_dir, path)) if not entry.startswith("."))
        ),
    )


boukensha.repl(block=register_tools)
