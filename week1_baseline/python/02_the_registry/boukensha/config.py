import os
from pathlib import Path

import yaml
from dotenv import load_dotenv


class Config:
    """Loads Boukensha settings from an external ``.boukensha/`` directory.

    The config directory is resolved in this order:
      1. ``BOUKENSHA_DIR`` environment variable
      2. ``~/.boukensha`` (default)
    """

    # Default location for a real install.
    DEFAULT_DIR = Path.home() / ".boukensha"

    # Default prompts shipped alongside the library code (00_config/prompts).
    PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"

    def __init__(self):
        self.dir = self._resolve_dir()
        self._load_env()
        self.settings = self._load_settings()

    # ---------- tasks -----------------------------------------------------

    def tasks(self, name=None):
        """Return the full tasks mapping, or one task's settings by name."""
        all_tasks = self.dig("tasks") or {}
        if name is None:
            return all_tasks
        return all_tasks.get(str(name))

    @property
    def user_prompts_dir(self):
        """The user's prompts directory for per task prompt overrides."""
        return self.dir / "prompts"

    # ---------- MUD connection --------------------------------------------

    @property
    def mud_host(self):
        return self.dig("mud", "host") or "localhost"

    @property
    def mud_port(self):
        return self.dig("mud", "port") or 4000

    @property
    def mud_username(self):
        return self.dig("mud", "username")

    @property
    def mud_password(self):
        return self.dig("mud", "password")

    # ---------- low level helpers -----------------------------------------

    def dig(self, *keys):
        """Fetch a nested key path from settings, e.g. dig("mud", "host")."""
        node = self.settings
        for key in keys:
            if isinstance(node, dict):
                node = node.get(str(key))
            else:
                return None
        return node

    def __str__(self):
        return f"#<Boukensha::Config dir={self.dir} tasks={','.join(self.tasks().keys())}>"

    def __repr__(self):
        return self.__str__()

    # ---------- private ---------------------------------------------------

    def _resolve_dir(self):
        raw = os.environ.get("BOUKENSHA_DIR") or self.DEFAULT_DIR
        return Path(raw).expanduser().resolve()

    def _load_env(self):
        env_file = self.dir / ".env"
        if env_file.exists():
            load_dotenv(env_file)

    def _load_settings(self):
        settings_file = self.dir / "settings.yaml"
        if settings_file.exists():
            return yaml.safe_load(settings_file.read_text()) or {}
        return {}
