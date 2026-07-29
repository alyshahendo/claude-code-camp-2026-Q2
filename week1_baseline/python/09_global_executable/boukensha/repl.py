import sys

from .agent import Agent
from .errors import ApiError, LoopError


class Repl:
    """The interactive session loop.

    It wraps the same primitives as a single ``boukensha.run`` call, but instead
    of running once it stays alive: it reads a task from the user, runs the
    agent, prints the reply, and loops back to the prompt.

    The Context is shared across every turn so conversation history accumulates
    naturally: the agent sees the full transcript each time it is called.

    Built-in commands (not sent to the agent):
        /help    print the command list
        /quiet   suppress detailed logging
        /loud    re-enable logging
        /clear   wipe conversation history (tools stay registered)
        /exit    leave the REPL
        /quit    alias for /exit
    """

    PROMPT = "boukensha> "

    HELP = (
        "Commands:\n"
        "  /quiet   suppress logging output\n"
        "  /loud    re-enable logging output\n"
        "  /clear   wipe conversation history (tools stay)\n"
        "  /exit    leave the REPL\n"
        "  /help    show this message\n"
    )

    def __init__(
        self,
        context,
        registry,
        builder,
        client,
        logger,
        config_dir=None,
        provider=None,
        model=None,
        version=None,
        api_key=None,
        task_settings=None,
        max_iterations=None,
        max_output_tokens=None,
    ):
        self._context = context
        self._registry = registry
        self._builder = builder
        self._client = client
        self._logger = logger
        self._task_settings = task_settings
        self._max_iterations = max_iterations
        self._max_output_tokens = max_output_tokens
        self._config_dir = config_dir
        self._provider = provider
        self._model = model
        self._version = version
        self._api_key = api_key
        self._turn = 0

    def start(self):
        print(self._banner())

        while True:
            print(self.PROMPT, end="", flush=True)

            line = sys.stdin.readline()
            if line == "":  # EOF / Ctrl-D
                break

            text = line.strip()
            if not text:
                continue

            if text in ("/exit", "/quit"):
                print("Goodbye.")
                break
            if text == "/help":
                print(self.HELP)
                continue
            if text == "/quiet":
                import boukensha

                boukensha.enable_quiet()
                print("(logging suppressed — type /loud to re-enable)")
                continue
            if text == "/loud":
                import boukensha

                boukensha.disable_quiet()
                print("(logging enabled)")
                continue
            if text == "/clear":
                self._context.clear_messages()
                self._turn = 0
                print("(conversation history cleared)")
                continue

            self._run_turn(text)

    # ---------- private ---------------------------------------------------

    def _banner(self):
        ver = self._version or "?.?.?"

        return (
            "\n"
            "╔══════════════════════════════════════╗\n"
            f"║  BOUKENSHA MUD Assistant (v{ver}){' ' * (9 - len(ver))}║\n"
            "╚══════════════════════════════════════╝\n"
            f"  config:        {self._config_dir or '(default)'}\n"
            f"  provider:      {self._provider or '(default)'}\n"
            f"  model:         {self._model or '(default)'}\n"
            "\n"
            "  /quiet or /loud   toggle logging\n"
            "  /clear           reset conversation history\n"
            "  /exit or /quit    leave the REPL\n"
        )

    def _run_turn(self, text):
        try:
            self._turn += 1
            self._logger.turn(n=self._turn)

            self._context.add_message("user", text)

            agent = Agent(
                context=self._context,
                registry=self._registry,
                builder=self._builder,
                client=self._client,
                logger=self._logger,
                task_settings=self._task_settings,
                max_iterations=self._max_iterations,
                max_output_tokens=self._max_output_tokens,
            )
            result = agent.run()

            # Print the final response outside of the logger so it is always
            # visible, even when quiet mode is active.
            print()
            print(result)
        except LoopError as error:
            print(f"\n[error] {error}")
        except ApiError as error:
            print(f"\n[error] API call failed: {error}")
