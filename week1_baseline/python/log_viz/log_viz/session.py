"""Parse a Boukensha session .jsonl log into an ordered list of entries
suitable for rendering as a human-readable transcript.
"""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class Entry:
    type: str
    text: Optional[str] = None
    usage: Optional[dict] = None
    turn: Optional[int] = None
    iteration: Optional[int] = None
    tool_name: Optional[str] = None
    tool_args: Optional[dict] = None
    tool_result: Optional[str] = None
    tool_ok: Optional[bool] = None
    tool_error: Optional[str] = None
    stop_reason: Optional[str] = None
    reason: Optional[str] = None
    iterations: Optional[int] = None
    tokens: Optional[int] = None
    before: Optional[int] = None
    dropped: Optional[int] = None
    running_turn_tokens: Optional[int] = None
    redacted: Optional[bool] = None
    task: Optional[str] = None
    provider: Optional[str] = None
    model: Optional[str] = None
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    cost_usd: Optional[float] = None
    usage_unit: Optional[str] = None
    usage_level: Optional[str] = None


@dataclass
class UsagePoint:
    turn: Optional[int] = None
    iteration: Optional[int] = None
    input: int = 0
    output: int = 0
    cache_read: int = 0
    cache_creation: int = 0
    running: int = 0
    at: Optional[str] = None
    task: Optional[str] = None
    provider: Optional[str] = None
    model: Optional[str] = None
    cost_usd: Optional[float] = None
    usage_unit: Optional[str] = None
    usage_level: Optional[str] = None


def _to_i(value):
    """Ruby-style #to_i: nil/invalid become 0."""
    if value is None:
        return 0
    try:
        return int(value)
    except (ValueError, TypeError):
        return 0


class Session:
    # Per-MTok input/output rates. Cache reads bill at ~0.1x input, cache
    # writes at ~1.25x input. Unknown models return None cost (rendered as —).
    MODEL_PRICES = {
        "claude-fable-5": {"input": 10.0, "output": 50.0},
        "claude-opus-4-8": {"input": 5.0, "output": 25.0},
        "claude-opus-4-7": {"input": 5.0, "output": 25.0},
        "claude-opus-4-6": {"input": 5.0, "output": 25.0},
        "claude-sonnet-4-6": {"input": 3.0, "output": 15.0},
        "claude-haiku-4-5": {"input": 1.0, "output": 5.0},
    }

    @classmethod
    def load(cls, path):
        session = cls(path)
        session.parse()
        return session

    def __init__(self, path):
        self.path = str(path)
        self.id = Path(path).stem
        self.entries = []
        self.started_at = None
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.snapshot = {}
        self.usage_series = []
        self.peak_input_tokens = 0

    def parse(self):
        current_turn = 0
        current_iteration = 0
        pending_user = True
        pending_calls = []
        running_turn = 0  # cumulative input+output within the current turn

        with open(self.path) as handle:
            for raw in handle:
                line = raw.strip()
                if not line:
                    continue

                event = json.loads(line)
                phase = event.get("phase")

                if phase == "session_start":
                    self.started_at = event.get("at")
                    self.snapshot = event  # carries the limits/model denominators
                elif phase == "turn":
                    current_turn = event["n"]
                    pending_user = True
                    running_turn = 0
                elif phase == "iteration":
                    current_iteration = event["n"]
                elif phase == "prompt":
                    if not pending_user:
                        continue
                    messages = event.get("messages")
                    message = messages[-1] if messages else None
                    if message and message.get("role") == "user":
                        self.entries.append(
                            Entry(
                                type="user",
                                text=self._extract_text(message.get("content")),
                                turn=current_turn,
                                iteration=current_iteration,
                            )
                        )
                    pending_user = False
                elif phase == "compaction":
                    self.entries.append(
                        Entry(
                            type="compaction",
                            before=event.get("before"),
                            dropped=event.get("dropped"),
                            turn=current_turn,
                            iteration=current_iteration,
                        )
                    )
                elif phase == "reasoning":
                    self.entries.append(
                        Entry(
                            type="reasoning",
                            text=event.get("text"),
                            redacted=event.get("redacted"),
                            turn=current_turn,
                            iteration=current_iteration,
                        )
                    )
                elif phase == "plan":
                    self.entries.append(
                        Entry(
                            type="plan",
                            text=event.get("text"),
                            turn=current_turn,
                            iteration=current_iteration,
                        )
                    )
                elif phase == "response":
                    usage = event.get("usage")
                    if usage:
                        input_tokens = event.get("input_tokens")
                        if input_tokens is None:
                            input_tokens = usage.get("input_tokens")
                        output_tokens = event.get("output_tokens")
                        if output_tokens is None:
                            output_tokens = usage.get("output_tokens")
                        input_tokens = _to_i(input_tokens)
                        output_tokens = _to_i(output_tokens)
                        self.total_input_tokens += input_tokens
                        self.total_output_tokens += output_tokens
                        running_turn += input_tokens + output_tokens
                        if input_tokens > self.peak_input_tokens:
                            self.peak_input_tokens = input_tokens
                        self.usage_series.append(
                            UsagePoint(
                                turn=current_turn,
                                iteration=current_iteration,
                                input=input_tokens,
                                output=output_tokens,
                                cache_read=_to_i(usage.get("cache_read_input_tokens")),
                                cache_creation=_to_i(usage.get("cache_creation_input_tokens")),
                                running=running_turn,
                                at=event.get("at"),
                                task=event.get("task"),
                                provider=event.get("provider"),
                                model=event.get("model"),
                                cost_usd=self._numeric(event.get("cost_usd")),
                                usage_unit=event.get("usage_unit"),
                                usage_level=event.get("usage_level"),
                            )
                        )
                    self.entries.append(
                        Entry(
                            type="assistant",
                            text=event.get("text"),
                            usage=usage,
                            stop_reason=event.get("stop_reason"),
                            running_turn_tokens=running_turn,
                            task=event.get("task"),
                            provider=event.get("provider"),
                            model=event.get("model"),
                            input_tokens=event.get("input_tokens"),
                            output_tokens=event.get("output_tokens"),
                            cost_usd=self._numeric(event.get("cost_usd")),
                            usage_unit=event.get("usage_unit"),
                            usage_level=event.get("usage_level"),
                            turn=current_turn,
                            iteration=current_iteration,
                        )
                    )
                elif phase == "tool_call":
                    pending_calls.append({"name": event.get("name"), "args": event.get("args")})
                elif phase == "tool_result":
                    call = pending_calls.pop(0) if pending_calls else {}
                    self.entries.append(
                        Entry(
                            type="tool",
                            tool_name=event.get("name") or call.get("name"),
                            tool_args=call.get("args"),
                            tool_result=event.get("result"),
                            tool_ok=event.get("ok", True),
                            tool_error=event.get("error"),
                            turn=current_turn,
                            iteration=current_iteration,
                        )
                    )
                elif phase == "turn_end":
                    self.entries.append(
                        Entry(
                            type="turn_end",
                            reason=event.get("reason"),
                            iterations=event.get("iterations"),
                            tokens=event.get("tokens"),
                            turn=current_turn,
                            iteration=current_iteration,
                        )
                    )

    # ---- counts ----------------------------------------------------------

    @property
    def turn_count(self):
        return max((_to_i(e.turn) for e in self.entries), default=0) + 1

    @property
    def iteration_count(self):
        return max((_to_i(e.iteration) for e in self.entries), default=0)

    # ---- denominators sourced from the session_start snapshot ------------

    @property
    def iteration_max(self):
        return self.snapshot.get("max_iterations")

    @property
    def max_turn_tokens(self):
        return self.snapshot.get("max_turn_tokens")

    @property
    def context_window(self):
        return self.snapshot.get("context_window")

    @property
    def model(self):
        return self.snapshot.get("model")

    @property
    def provider(self):
        return self.snapshot.get("provider")

    @property
    def response_models(self):
        return list(dict.fromkeys(p.model for p in self.usage_series if p.model is not None))

    @property
    def response_providers(self):
        return list(dict.fromkeys(p.provider for p in self.usage_series if p.provider is not None))

    @property
    def task_names(self):
        return list(dict.fromkeys(p.task for p in self.usage_series if p.task is not None))

    @property
    def model_summary(self):
        labels = list(
            dict.fromkeys(
                label
                for label in (self._model_label(p.provider, p.model) for p in self.usage_series)
                if label is not None
            )
        )
        if not labels:
            single = self._model_label(self.provider, self.model)
            labels = [single] if single is not None else []
        return ", ".join(labels) if len(labels) <= 2 else f"{len(labels)} models"

    # ---- per-turn outcomes ----------------------------------------------

    @property
    def turn_ends(self):
        return [e for e in self.entries if e.type == "turn_end"]

    @property
    def end_reason(self):
        ends = self.turn_ends
        return ends[-1].reason if ends else None

    @property
    def stopped(self):
        return self.end_reason is not None and self.end_reason != "completed"

    @property
    def last_iterations(self):
        ends = self.turn_ends
        return ends[-1].iterations if ends and ends[-1].iterations is not None else self.iteration_count

    @property
    def turn_tokens(self):
        ends = self.turn_ends
        if ends and ends[-1].tokens is not None:
            return ends[-1].tokens
        return self.total_input_tokens + self.total_output_tokens

    # ---- per-turn rollup -------------------------------------------------

    @property
    def turns(self):
        rows = [
            {"n": e.turn, "iterations": e.iterations, "tokens": _to_i(e.tokens), "reason": e.reason}
            for e in self.turn_ends
        ]
        if rows:
            return rows
        return [
            {
                "n": max((_to_i(e.turn) for e in self.entries), default=0),
                "iterations": self.iteration_count,
                "tokens": self.total_input_tokens + self.total_output_tokens,
                "reason": self.end_reason,
            }
        ]

    def limit_reason(self, reason):
        return reason is not None and reason != "completed"

    @property
    def largest_turn(self):
        rows = self.turns
        return max(rows, key=lambda t: t["tokens"]) if rows else None

    @property
    def busiest_turn(self):
        rows = self.turns
        return max(rows, key=lambda t: _to_i(t["iterations"])) if rows else None

    @property
    def any_limit_tripped(self):
        return any(self.limit_reason(t["reason"]) for t in self.turns)

    @property
    def turn_count_real(self):
        return len(self.turns)

    # ---- cost estimate ---------------------------------------------------

    @property
    def estimated_cost(self):
        costs = [c for c in (self._point_cost(p) for p in self.usage_series) if c is not None]
        return sum(costs) if costs else None

    @property
    def cost_breakdown(self):
        rows = {}
        for p in self.usage_series:
            key = (
                p.task or "unknown",
                p.provider or self.provider or "unknown",
                p.model or self.model or "unknown",
            )
            row = rows.get(key)
            if row is None:
                row = rows[key] = {
                    "task": key[0], "provider": key[1], "model": key[2],
                    "calls": 0, "input": 0, "output": 0, "cost": 0.0, "cost_known": True,
                }
            row["calls"] += 1
            row["input"] += _to_i(p.input)
            row["output"] += _to_i(p.output)
            cost = self._point_cost(p)
            if cost is not None:
                row["cost"] += cost
            else:
                row["cost_known"] = False
        return sorted(
            rows.values(),
            key=lambda row: (-row["cost"], row["task"], row["provider"], row["model"]),
        )

    @property
    def task(self):
        for e in self.entries:
            if e.type == "user":
                return e.text
        return None

    @property
    def final_response(self):
        for e in reversed(self.entries):
            if (
                e.type == "assistant"
                and e.stop_reason != "tool_use"
                and not str(e.text or "").startswith("(tool use")
            ):
                return e.text
        return None

    # ---- private ---------------------------------------------------------

    def _extract_text(self, content):
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts = []
            for block in content:
                kind = block.get("type")
                if kind == "text":
                    parts.append(block.get("text"))
                elif kind == "tool_use":
                    parts.append(f"[tool_use: {block.get('name')}]")
                elif kind == "tool_result":
                    parts.append("[tool_result]")
                else:
                    parts.append(str(block))
            return "\n".join("" if p is None else p for p in parts)
        return str(content)

    def _numeric(self, value):
        if value is None:
            return None
        try:
            return float(value)
        except (ValueError, TypeError):
            return None

    def _model_label(self, provider, model):
        if provider is None and model is None:
            return None
        return " / ".join(part for part in (provider, model) if part is not None)

    def _point_cost(self, point):
        if point.cost_usd is not None:
            return point.cost_usd

        rates = self.MODEL_PRICES.get(point.model or self.model)
        if not rates:
            return None

        input_rate = rates["input"] / 1_000_000.0
        output_rate = rates["output"] / 1_000_000.0
        return (
            point.input * input_rate
            + point.output * output_rate
            + point.cache_read * input_rate * 0.1
            + point.cache_creation * input_rate * 1.25
        )
