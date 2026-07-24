from . import backends
from .agent import Agent
from .client import Client
from .config import Config
from .context import Context
from .errors import ApiError, UnknownToolError, UnsupportedModelError
from .logger import Logger
from .message import Message
from .prompt_builder import PromptBuilder
from .registry import Registry
from .tasks import Player
from .tool import Tool

__all__ = [
    "Config",
    "Player",
    "Tool",
    "Message",
    "Context",
    "Registry",
    "PromptBuilder",
    "Client",
    "Agent",
    "Logger",
    "backends",
    "UnknownToolError",
    "UnsupportedModelError",
    "ApiError",
    "config",
    "enable_quiet",
    "disable_quiet",
    "is_quiet",
    "enable_debug",
    "is_debug",
]

# Package-level singleton state, mirroring the Ruby module methods on
# ``Boukensha`` (config, quiet!/loud!/quiet?, debug!/debug?). Python has no
# ``!``/``?`` in identifiers, so the mutators are ``enable_*``/``disable_*`` and
# the predicates are ``is_*``.
_config = None
_quiet = False
_debug = False


def config():
    """Return the memoized package Config, creating it on first use."""
    global _config
    if _config is None:
        _config = Config()
    return _config


def enable_quiet():
    global _quiet
    _quiet = True


def disable_quiet():
    global _quiet
    _quiet = False


def is_quiet():
    return _quiet


def enable_debug():
    global _debug
    _debug = True


def is_debug():
    return _debug
