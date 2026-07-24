import json
import re
import secrets
from datetime import datetime, timezone
from pathlib import Path


class Logger:
    """Records each agent run as structured JSON Lines.

    This is a file logger, not user-facing display output. Each instance creates
    a session id and writes one ``.jsonl`` file for that session under
    ``.boukensha/sessions/``. Every line is a complete JSON object with
    ``session_id``, ``at``, and ``phase`` fields plus phase-specific data, which
    keeps the logs grep/tail friendly and machine readable.
    """

    DEFAULT_SESSION_DIR = "sessions"

    def __init__(self, session_id=None, dir=None, log=None, snapshot=None):
        self.session_id = session_id or self._generate_session_id()
        base = Path(dir) if dir else self._default_dir()
        self.path = Path(log) if log else base / f"{self.session_id}.jsonl"

        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._log_io = open(self.path, "a")
        self._write_log({"phase": "session_start", **(snapshot or {})})

    def iteration(self, n, max):
        self._write_log({"phase": "iteration", "n": n, "max": max})

    def limit_reached(self, kind, n, max):
        self._write_log({"phase": "limit_reached", "kind": kind, "n": n, "max": max})

    def turn_end(self, reason, iterations, tokens=None):
        self._write_log(
            {"phase": "turn_end", "reason": reason, "iterations": iterations, "tokens": tokens}
        )

    def prompt(self, messages, tools):
        self._write_log(
            {
                "phase": "prompt",
                "message_count": len(messages),
                "messages": [self._serialize_message(m) for m in messages],
                "tool_count": len(tools),
                "tools": list(tools.keys()),
            }
        )

    def tool_call(self, name, args):
        self._write_log({"phase": "tool_call", "name": name, "args": args})

    def tool_result(self, name, result, ok=True, error=None):
        self._write_log(
            {"phase": "tool_result", "name": name, "result": str(result), "ok": ok, "error": error}
        )

    def response(self, text, usage=None, stop_reason=None, task=None, backend=None):
        self._write_log(
            {
                "phase": "response",
                "text": str(text).strip(),
                "usage": usage,
                "stop_reason": stop_reason,
                **self._execution_metadata(task=task, backend=backend, usage=usage),
            }
        )

    def raw(self, data):
        from . import is_debug

        if not is_debug():
            return

        self._write_log({"phase": "raw", "data": data})

    def close(self):
        if self._log_io:
            self._log_io.close()

    # ---------- private ---------------------------------------------------

    def _default_dir(self):
        from . import config

        return Path(config().dir) / self.DEFAULT_SESSION_DIR

    def _write_log(self, event):
        line = json.dumps({**event, "session_id": self.session_id, "at": self._now_iso8601()})
        self._log_io.write(line + "\n")
        self._log_io.flush()

    def _generate_session_id(self):
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        return f"{stamp}-{secrets.token_hex(4)}"

    def _now_iso8601(self):
        # Local time with UTC offset, seconds precision (matches Ruby Time#iso8601).
        return datetime.now().astimezone().isoformat(timespec="seconds")

    def _serialize_message(self, msg):
        return {"role": msg.role, "content": msg.content}

    def _execution_metadata(self, task, backend, usage):
        if not (task or backend or usage):
            return {}

        tokens = self._usage_tokens(usage)
        metadata = {
            "task": self._task_name(task),
            "provider": self._provider_name(backend),
            "model": getattr(backend, "model", None),
            "usage_unit": backend.usage_unit if self._responds_to(backend, "usage_unit") else None,
            "usage_level": backend.usage_level if self._responds_to(backend, "usage_level") else None,
            "input_tokens": tokens["input"],
            "output_tokens": tokens["output"],
            "cost_usd": self._estimate_cost(backend, tokens),
        }
        return {key: value for key, value in metadata.items() if value is not None}

    def _task_name(self, task):
        if task is None:
            return None
        return task.task_name() if hasattr(task, "task_name") else str(task)

    def _provider_name(self, backend):
        if backend is None:
            return None
        # Snake-cases the backend class name, so OllamaCloud -> "ollama_cloud"
        # and OpenAI -> "open_ai" (matching the Ruby reference exactly).
        name = type(backend).__name__
        return re.sub(r"([a-z\d])([A-Z])", r"\1_\2", name).lower()

    def _usage_tokens(self, usage):
        usage = usage or {}
        return {
            "input": self._first_integer(
                usage, "input_tokens", "prompt_tokens", "promptTokenCount", "prompt_eval_count"
            ),
            "output": self._first_integer(
                usage, "output_tokens", "completion_tokens", "candidatesTokenCount", "eval_count"
            ),
        }

    def _first_integer(self, data, *keys):
        for key in keys:
            value = data.get(key)
            if value is not None:
                try:
                    return int(value)
                except (ValueError, TypeError):
                    return None
        return None

    def _estimate_cost(self, backend, tokens):
        if not self._responds_to(backend, "estimate_cost"):
            return None
        if tokens["input"] is None or tokens["output"] is None:
            return None
        return backend.estimate_cost(input_tokens=tokens["input"], output_tokens=tokens["output"])

    @staticmethod
    def _responds_to(obj, name):
        return obj is not None and hasattr(obj, name)
