import os
from types import SimpleNamespace

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
from .repl import Repl
from .run_dsl import RunDSL
from .tasks import Player
from .tool import Tool
from .version import VERSION

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
    "Repl",
    "VERSION",
    "backends",
    "UnknownToolError",
    "UnsupportedModelError",
    "ApiError",
    "LoopError",
    "run",
    "repl",
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


def _construct_backend(backend, api_key, model, ollama_host):
    if backend == "anthropic":
        return backends.Anthropic(api_key=api_key, model=model)
    if backend == "openai":
        return backends.OpenAI(api_key=api_key, model=model)
    if backend == "gemini":
        return backends.Gemini(api_key=api_key, model=model)
    if backend == "ollama":
        return backends.Ollama(host=ollama_host, model=model)
    if backend == "ollama_cloud":
        return backends.OllamaCloud(api_key=api_key, model=model)
    raise ValueError(
        f"Unknown backend {backend!r}. Use 'anthropic', 'openai', 'gemini', "
        "'ollama', or 'ollama_cloud'."
    )


def _build_session(system, model, backend, api_key, ollama_host, log, max_output_tokens, block):
    """Shared wiring for ``run`` and ``repl``: resolve config defaults, build the
    context/registry, run the tool-registration block, and construct the backend,
    prompt builder, client, and logger. Returns everything the caller needs.
    """
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

    builder = PromptBuilder(ctx, _construct_backend(backend, api_key, model, ollama_host))
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
    return SimpleNamespace(
        cfg=cfg,
        task_settings=task_settings,
        ctx=ctx,
        registry=registry,
        builder=builder,
        client=client,
        logger=logger,
        backend=backend,
        model=model,
        api_key=api_key,
        max_iterations=effective_max_iterations,
        max_output_tokens=effective_max_output_tokens,
    )


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
    """One-shot run: send a single task, get a response, return.

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
    session = None
    try:
        session = _build_session(
            system, model, backend, api_key, ollama_host, log, max_output_tokens, block
        )
        agent = Agent(
            context=session.ctx,
            registry=session.registry,
            builder=session.builder,
            client=session.client,
            logger=session.logger,
            task_settings=session.task_settings,
            max_iterations=session.max_iterations,
            max_output_tokens=session.max_output_tokens,
        )
        session.ctx.add_message("user", task)
        return agent.run()
    finally:
        if session is not None:
            session.logger.close()


def repl(
    system=None,
    model=None,
    backend=None,
    api_key=None,
    ollama_host="http://localhost:11434",
    log=None,
    max_output_tokens=None,
    block=None,
):
    """Interactive REPL: register tools once, then loop — reading tasks from
    stdin, running the agent, and printing replies — until the user types exit or
    sends EOF.

    Conversation history accumulates across every turn so the agent always sees
    the full transcript. Same options as :func:`run`, minus ``task`` (the user
    supplies tasks interactively).
    """
    session = None
    try:
        session = _build_session(
            system, model, backend, api_key, ollama_host, log, max_output_tokens, block
        )
        Repl(
            context=session.ctx,
            registry=session.registry,
            builder=session.builder,
            client=session.client,
            logger=session.logger,
            task_settings=session.task_settings,
            max_iterations=session.max_iterations,
            max_output_tokens=session.max_output_tokens,
            config_dir=session.cfg.dir,
            provider=session.backend,
            model=session.model,
            version=VERSION,
            api_key=session.api_key,
        ).start()
    except KeyboardInterrupt:
        print("\nInterrupted.")
    finally:
        if session is not None:
            session.logger.close()

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
