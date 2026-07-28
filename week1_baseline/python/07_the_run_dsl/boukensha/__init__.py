import os

from . import backends
from .agent import Agent
from .client import Client
from .config import Config
from .context import Context
from .errors import ApiError, LoopError, UnknownToolError, UnsupportedModelError
from .logger import Logger
from .message import Message
from .prompt_builder import PromptBuilder
from .registry import Registry
from .run_dsl import RunDSL
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
    "RunDSL",
    "backends",
    "UnknownToolError",
    "UnsupportedModelError",
    "ApiError",
    "LoopError",
    "run",
    "config",
    "enable_quiet",
    "disable_quiet",
    "is_quiet",
    "enable_debug",
    "is_debug",
]

_ENV_KEY_BY_BACKEND = {
    "anthropic": "ANTHROPIC_API_KEY",
    "openai": "OPENAI_API_KEY",
    "gemini": "GEMINI_API_KEY",
    "ollama_cloud": "OLLAMA_API_KEY",
}


def run(
    task,
    system=None,
    model=None,
    backend=None,
    api_key=None,
    ollama_host="http://localhost:11434",
    log=None,
    max_output_tokens=None,
    block=None,
):
    """The top-level entry point. Wires together every primitive so the caller
    only has to describe *what* to do, not *how* to plumb it.

        def define(dsl):
            dsl.tool(
                "read_file",
                description="Read a file from disk",
                parameters={"path": {"type": "string", "description": "File path"}},
                block=lambda path: open(path).read(),
            )

        result = boukensha.run(task="Summarise boukensha/__init__.py", block=define)

    ``block`` receives a :class:`RunDSL` (the Python stand-in for Ruby's
    ``instance_eval`` block). ``task`` is the user message; the other keyword
    arguments override defaults sourced from config.
    """
    logger = None
    try:
        cfg = config()  # loads .env; populates os.environ
        task_class = Player
        task_settings = cfg.tasks(task_class.task_name())
        if system is None:
            system = task_class.system_prompt(
                task_settings,
                user_prompts_dir=cfg.user_prompts_dir,
                default_prompts_dir=Config.PROMPTS_DIR,
            )
        if model is None:
            model = task_class.model(task_settings)
        if backend is None:
            backend = task_class.provider(task_settings)
        if api_key is None:
            env_key = _ENV_KEY_BY_BACKEND.get(backend)
            api_key = os.environ.get(env_key) if env_key else None

        ctx = Context(task=task_class, system=system)
        registry = Registry(ctx)

        if block is not None:
            block(RunDSL(registry))

        if backend == "anthropic":
            be = backends.Anthropic(api_key=api_key, model=model)
        elif backend == "openai":
            be = backends.OpenAI(api_key=api_key, model=model)
        elif backend == "gemini":
            be = backends.Gemini(api_key=api_key, model=model)
        elif backend == "ollama":
            be = backends.Ollama(host=ollama_host, model=model)
        elif backend == "ollama_cloud":
            be = backends.OllamaCloud(api_key=api_key, model=model)
        else:
            raise ValueError(
                f"Unknown backend {backend!r}. Use 'anthropic', 'openai', 'gemini', "
                "'ollama', or 'ollama_cloud'."
            )

        builder = PromptBuilder(ctx, be)
        client = Client(builder)
        effective_max_iterations = task_class.max_iterations(task_settings)
        effective_max_output_tokens = max_output_tokens or task_class.max_output_tokens(task_settings)
        logger = Logger(
            log=log,
            snapshot={
                "task": task_class.task_name(),
                "max_iterations": effective_max_iterations,
                "max_output_tokens": effective_max_output_tokens,
                "model": model,
                "provider": backend,
            },
        )
        agent = Agent(
            context=ctx,
            registry=registry,
            builder=builder,
            client=client,
            logger=logger,
            task_settings=task_settings,
            max_iterations=effective_max_iterations,
            max_output_tokens=effective_max_output_tokens,
        )

        ctx.add_message("user", task)
        return agent.run()
    finally:
        if logger is not None:
            logger.close()

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
