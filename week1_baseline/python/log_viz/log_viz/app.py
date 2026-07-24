"""Flask app that turns Boukensha session .jsonl logs into a browser transcript.

The Python port of the Ruby Sinatra `LogViz::App`. View helpers are registered
as Jinja globals; helpers that emit HTML return ``Markup`` so Jinja does not
double-escape them (the Ruby ERB templates were not auto-escaped).
"""

import glob
import math
import os
from datetime import datetime
from pathlib import Path

from flask import Flask, abort, render_template
from markupsafe import Markup

from . import ansi
from .session import Session, _to_i


def _to_f(value):
    if value is None:
        return 0.0
    try:
        return float(value)
    except (ValueError, TypeError):
        return 0.0


def _round_half_up(value):
    # Ruby Float#round rounds halves away from zero; all inputs here are positive.
    return math.floor(value + 0.5)


# ---------- view helpers (registered as Jinja globals) --------------------


def format_time(iso):
    if not iso:
        return "?"
    try:
        return datetime.fromisoformat(iso).strftime("%Y-%m-%d %H:%M:%S %z")
    except (ValueError, TypeError):
        return iso


def truncate(text, length=100):
    flat = " ".join(str(text or "").split()).strip()
    return f"{flat[:length]}…" if len(flat) > length else flat


def format_args(args):
    if not args:
        return ""
    return ", ".join(f"{key}: {value!r}" for key, value in args.items())


def ansi_html(text):
    return Markup(ansi.to_html(text))


def text_html(text):
    return Markup(ansi.escape_html(text))


def fmt_tokens(n):
    n = _to_i(n)
    return f"{n / 1000.0:.1f}k" if n >= 1000 else str(n)


def pct(used, max_):
    m = _to_i(max_)
    return min(_round_half_up(_to_f(used) / m * 100), 100) if m > 0 else 0


def pct_raw(used, max_):
    m = _to_i(max_)
    return _round_half_up(_to_f(used) / m * 100) if m > 0 else 0


def progress_bar(used, max_, label, danger=False):
    width = pct(used, max_)
    klass = "bar-fill danger" if danger else "bar-fill"
    return Markup(
        '<div class="budget">\n'
        f'  <div class="budget-label">{label}</div>\n'
        f'  <div class="bar"><div class="{klass}" style="width: {width}%"></div></div>\n'
        "</div>\n"
    )


def fmt_cost(n):
    return Markup("&mdash;") if n is None else Markup(f"${n:.4f}")


def fmt_cost_cell(cost, known=True):
    if cost is None or not known:
        return Markup("&mdash;")
    return fmt_cost(cost)


def any_turn_reason(turns, reason):
    return any(turn["reason"] == reason for turn in turns)


def ctx_chip(usage, running, context_window, max_turn_tokens, model=None, provider=None, cost_usd=None):
    # In-transcript chip: live context size as a mini-bar scaled to the context
    # window, plus the turn spend accumulating toward its cap.
    if not usage:
        return Markup("")

    input_tokens = _to_i(usage.get("input_tokens"))
    out = _to_i(usage.get("output_tokens"))
    cache = _to_i(usage.get("cache_read_input_tokens"))

    parts = []
    # Turn spend first and bar-backed — it's what trips max_tokens.
    if _to_i(max_turn_tokens) > 0:
        danger = " danger" if _to_i(running) > _to_i(max_turn_tokens) else ""
        parts.append(f'<span class="ctx-turn{danger}">turn {fmt_tokens(running)}/{fmt_tokens(max_turn_tokens)}</span>')
        parts.append(
            f'<span class="ctx-bar"><span class="ctx-bar-fill{danger}" '
            f'style="width: {pct(running, max_turn_tokens)}%"></span></span>'
        )
    # Live context size second, with a smaller mini-bar.
    parts.append(f'<span class="ctx-amt">ctx {fmt_tokens(input_tokens)}</span>')
    if _to_i(context_window) > 0:
        parts.append(
            f'<span class="ctx-mini"><span class="ctx-mini-fill" '
            f'style="width: {pct(input_tokens, context_window)}%"></span></span>'
        )
    parts.append(f'<span class="ctx-out">+{fmt_tokens(out)} out</span>')
    if cache > 0:
        parts.append(f'<span class="ctx-cache">cached {fmt_tokens(cache)}</span>')
    if cost_usd is not None:
        parts.append(f'<span class="ctx-cost">{fmt_cost(cost_usd)}</span>')
    if provider or model:
        label = " / ".join(part for part in (provider, model) if part)
        parts.append(f'<span class="ctx-model">{label}</span>')

    return Markup(f'<span class="ctx-chip">{chr(10).join(parts)}</span>')


def sparkline(points, max_, width=640, height=48):
    # Inline SVG sparkline of per-iteration input_tokens across the session.
    if len(points) < 2:
        return Markup("")

    max_ = 1 if _to_i(max_) < 1 else _to_i(max_)
    step = width / (len(points) - 1)

    coords = " ".join(
        f"{round(i * step, 1)},{round(height - (_to_f(p.input) / max_ * (height - 4)) - 2, 1)}"
        for i, p in enumerate(points)
    )

    # Faint vertical rule at each turn's first iteration (after turn 1).
    rules = "".join(
        f'<line class="spark-turn" x1="{round(i * step, 1)}" y1="0" '
        f'x2="{round(i * step, 1)}" y2="{height}"/>'
        for i, p in enumerate(points)
        if i > 0 and p.iteration == 1
    )

    return Markup(
        f'<svg class="spark" viewBox="0 0 {width} {height}" preserveAspectRatio="none" '
        'role="img" aria-label="input tokens per iteration">\n'
        f"  {rules}\n"
        f'  <polyline class="spark-line" points="{coords}"/>\n'
        "</svg>\n"
    )


def _default_sessions_dir():
    return str(Path(__file__).resolve().parents[4] / ".boukensha" / "sessions")


def create_app():
    app = Flask(__name__, static_folder="static", static_url_path="")
    app.config["SESSIONS_DIR"] = os.environ.get("LOG_VIZ_SESSIONS_DIR", _default_sessions_dir())

    # Register every view helper so the templates can call them like Sinatra
    # helpers.
    app.jinja_env.globals.update(
        format_time=format_time,
        truncate=truncate,
        format_args=format_args,
        ansi_html=ansi_html,
        text_html=text_html,
        fmt_tokens=fmt_tokens,
        pct=pct,
        pct_raw=pct_raw,
        progress_bar=progress_bar,
        fmt_cost=fmt_cost,
        fmt_cost_cell=fmt_cost_cell,
        ctx_chip=ctx_chip,
        sparkline=sparkline,
        any_turn_reason=any_turn_reason,
    )

    def session_paths():
        pattern = os.path.join(app.config["SESSIONS_DIR"], "*.jsonl")
        return sorted(glob.glob(pattern), reverse=True)

    @app.route("/")
    def index():
        sessions = [Session.load(path) for path in session_paths()]
        return render_template(
            "index.html", sessions=sessions, sessions_dir=app.config["SESSIONS_DIR"]
        )

    @app.route("/sessions/<id>")
    def show_session(id):
        session_id = os.path.basename(id)
        path = os.path.join(app.config["SESSIONS_DIR"], f"{session_id}.jsonl")
        if not os.path.isfile(path):
            abort(404, f"Session not found: {session_id}")
        return render_template("session.html", session=Session.load(path))

    return app
