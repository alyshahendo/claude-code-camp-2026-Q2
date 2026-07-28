from .errors import ApiError
from .logger import Logger


class Agent:
    """The agent loop: send messages, dispatch tools, and know when to stop.

    Everything built before this (the structs, the registry, the prompt builder,
    the client) was setup. The loop is where the agent actually does work. It
    only ever sees the normalized ``parse_response`` shape, so it stays a single
    ``if stop_reason == "tool_use"`` branch regardless of provider.

    Every phase of the turn is recorded through the injected ``Logger``; the loop
    itself no longer prints to stdout.
    """

    # Default iteration ceiling. The enforced value comes from the
    # max_iterations constructor arg (sourced from Config at the run/repl path),
    # which falls back to this constant. 0 (or None) disables the ceiling.
    MAX_ITERATIONS = 25

    # The wind-down call is deliberately short and cheap.
    WRAP_UP_OUTPUT_TOKENS = 400
    WRAP_UP_DIRECTIVE = (
        "You have reached your action limit for this turn. Do not call any more tools.\n"
        "Briefly summarize what you accomplished, what is still unfinished, and the\n"
        "single next action you would take."
    )

    def __init__(
        self,
        context,
        registry,
        builder,
        client,
        logger=None,
        task_settings=None,
        max_iterations=None,
        max_output_tokens=None,
    ):
        self._context = context
        self._registry = registry
        self._builder = builder
        self._client = client
        self._logger = logger if logger is not None else Logger()
        self._max_iterations = self._resolve_max_iterations(task_settings, max_iterations)
        self._max_output_tokens = self._resolve_max_output_tokens(task_settings, max_output_tokens)
        self._iteration = 0

    def run(self):
        while True:
            # Limits are trigger thresholds, not hard caps: once we reach one we
            # stop starting new work iterations and make exactly one terminal
            # wind-down call instead of raising.
            if self._iteration_limit_reached():
                self._logger.limit_reached(
                    kind="max_iterations", n=self._iteration, max=self._max_iterations
                )
                return self._wrap_up("max_iterations")

            self._iteration += 1
            self._logger.iteration(n=self._iteration, max=self._max_iterations)
            self._logger.prompt(messages=self._context.messages, tools=self._context.tools)

            response = self._client.call(**self._call_opts())
            self._logger.raw(data=response)
            parsed = self._builder.parse_response(response)

            if parsed["stop_reason"] == "tool_use":
                self._handle_tool_calls(parsed["content"], response)
            else:
                text = self._extract_text(parsed["content"])
                self._log_response(text=text, response=response)
                self._logger.turn_end(reason="completed", iterations=self._iteration)
                return text

    # ---------- private ---------------------------------------------------

    def _resolve_max_iterations(self, task_settings, explicit):
        if explicit is not None:
            return int(explicit)
        if task_settings is not None and hasattr(self._context.task, "max_iterations"):
            return self._context.task.max_iterations(task_settings)
        return self.MAX_ITERATIONS

    def _resolve_max_output_tokens(self, task_settings, explicit):
        if explicit is not None:
            return explicit
        if task_settings is not None and hasattr(self._context.task, "max_output_tokens"):
            return self._context.task.max_output_tokens(task_settings)
        return None

    def _iteration_limit_reached(self):
        return self._max_iterations > 0 and self._iteration >= self._max_iterations

    # Per-call options shared by every model round-trip of the turn.
    def _call_opts(self):
        return {"max_output_tokens": self._max_output_tokens} if self._max_output_tokens else {}

    # One final, tools-disabled model call so the agent ends the turn in
    # character rather than aborting. Runs outside the counted loop: it never
    # re-checks the limits (so it cannot re-trigger) and does not increment
    # the iteration counter. Falls back to a deterministic message if the call
    # fails.
    def _wrap_up(self, reason):
        self._context.add_message("user", self.WRAP_UP_DIRECTIVE)
        try:
            response = self._client.call(tools=[], max_output_tokens=self.WRAP_UP_OUTPUT_TOKENS)
        except ApiError:
            message = self._fallback_message(reason)
            self._logger.turn_end(reason=reason, iterations=self._iteration)
            return message

        text = self._extract_text(self._builder.parse_response(response)["content"])
        if text.strip() == "":
            text = self._fallback_message(reason)
        self._log_response(text=text, response=response)
        self._logger.turn_end(reason=reason, iterations=self._iteration)
        return text

    def _fallback_message(self, reason):
        return (
            f"I reached my {self._max_iterations}-action limit for this turn before finishing "
            f"({reason}). Ask me to continue and I'll pick up from here."
        )

    def _extract_text(self, content):
        return "".join(block["text"] for block in content if block["type"] == "text")

    def _handle_tool_calls(self, content, response):
        tool_calls = [block for block in content if block["type"] == "tool_use"]

        reasoning = self._extract_text(content)
        if reasoning.strip() == "":
            plural = "" if len(tool_calls) == 1 else "s"
            reasoning = f"(tool use — {len(tool_calls)} call{plural})"
        self._log_response(text=reasoning, response=response)

        self._context.add_message("assistant", content)

        for block in tool_calls:
            name = block["name"]
            args = block["input"]
            use_id = block["id"]

            self._logger.tool_call(name=name, args=args)
            try:
                result = self._registry.dispatch(name, args)
                self._logger.tool_result(name=name, result=result, ok=True)
            except Exception as error:
                result = f"ERROR: {type(error).__name__}: {error}"
                self._logger.tool_result(name=name, result=result, ok=False, error=str(error))

            self._context.add_message("tool_result", str(result), tool_use_id=use_id)

    def _log_response(self, text, response):
        self._logger.response(
            text=text,
            usage=self._normalized_usage(response),
            stop_reason=response.get("stop_reason"),
            task=self._context.task,
            backend=self._builder.backend,
        )

    def _normalized_usage(self, response):
        if response.get("usage"):
            return response["usage"]
        if response.get("usageMetadata"):
            return response["usageMetadata"]

        usage = {}
        for key in ("prompt_eval_count", "eval_count"):
            if key in response:
                usage[key] = response[key]
        return usage or None
