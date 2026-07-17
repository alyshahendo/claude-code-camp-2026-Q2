#!/usr/bin/env python3
"""Persistent MUD session helper.

A CircleMUD/tbaMUD connection is stateful: your character stands in a room,
and every command mutates that live state. If the socket closes between
commands you get dumped back at the starting altar and lose combat, position,
and buffs. But an agent works in discrete tool calls, and a normal process
(a `nc` one-shot) dies the moment the call returns — taking the login with it.

This script bridges that gap. `start` spawns a detached **daemon** that holds
one TCP socket to the MUD and stays logged in. Every other subcommand is a
short-lived **client** that talks to the daemon over a Unix socket, so the
agent can `send` many commands across many tool calls while a single character
session stays alive the whole time.

    mud.py start          # daemon connects + logs in (idempotent)
    mud.py send "look"    # send a command, print the game's reply
    mud.py send "kill rabbit"
    mud.py read           # drain async chatter without sending anything
    mud.py status         # is the daemon up / logged in?
    mud.py transcript     # print the full session log
    mud.py stop           # shut the daemon down

Only the Python standard library is used, so the skill has no install step.
Connection defaults (host/port/user/pass) come from flags or MUD_* env vars.
"""

import argparse
import json
import os
import re
import socket
import sys
import threading
import time

# ---------------------------------------------------------------------------
# Configuration & runtime paths
# ---------------------------------------------------------------------------

DEFAULT_HOST = os.environ.get("MUD_HOST", "localhost")
DEFAULT_PORT = int(os.environ.get("MUD_PORT", "4000"))
DEFAULT_USER = os.environ.get("MUD_USER", "dummy")
DEFAULT_PASS = os.environ.get("MUD_PASS", "helloworld")


def runtime_dir(port):
    """Per-port runtime dir so sessions to different MUDs don't collide."""
    base = os.environ.get("MUD_RUNTIME_DIR") or os.path.join(
        os.environ.get("TMPDIR", "/tmp"), "mud_session"
    )
    d = os.path.join(base, str(port))
    os.makedirs(d, exist_ok=True)
    return d


def paths(port):
    d = runtime_dir(port)
    return {
        "sock": os.path.join(d, "control.sock"),
        "pid": os.path.join(d, "daemon.pid"),
        "log": os.path.join(d, "daemon.log"),
        "transcript": os.path.join(d, "transcript.log"),
    }


# ---------------------------------------------------------------------------
# Telnet IAC stripping
# ---------------------------------------------------------------------------
# CircleMUD interleaves telnet negotiation bytes (mostly echo toggling around
# the password prompt). We don't negotiate — we just discard IAC sequences so
# they never pollute the text buffer.

IAC, DONT, DO, WONT, WILL, SB, SE = 0xFF, 0xFE, 0xFD, 0xFC, 0xFB, 0xFA, 0xF0


def strip_iac(data: bytes) -> bytes:
    out = bytearray()
    i, n = 0, len(data)
    while i < n:
        b = data[i]
        if b == IAC:
            nxt = data[i + 1] if i + 1 < n else None
            if nxt is None:
                break
            if nxt == IAC:           # escaped literal 0xFF
                out.append(IAC)
                i += 2
            elif nxt in (WILL, WONT, DO, DONT):
                i += 3               # 3-byte negotiation
            elif nxt == SB:          # subnegotiation until IAC SE
                j = i + 2
                while j < n and not (data[j] == IAC and j + 1 < n and data[j + 1] == SE):
                    j += 1
                i = j + 2
            else:
                i += 2
        else:
            out.append(b)
            i += 1
    return bytes(out)


# ---------------------------------------------------------------------------
# Daemon: owns the live MUD socket
# ---------------------------------------------------------------------------

class MudDaemon:
    def __init__(self, host, port, user, password):
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.sock = None
        self.buffer = bytearray()
        self.lock = threading.Condition()
        self.last_recv = None
        self.closed = False
        self.logged_in = False
        self.p = paths(port)
        self._transcript = open(self.p["transcript"], "a", buffering=1)

    # ---- low-level socket plumbing ----

    def connect(self):
        self.sock = socket.create_connection((self.host, self.port), timeout=10)
        self.sock.settimeout(None)
        threading.Thread(target=self._reader, daemon=True).start()

    def _reader(self):
        try:
            while True:
                chunk = self.sock.recv(4096)
                if not chunk:
                    break
                text = strip_iac(chunk)
                if text:
                    with self.lock:
                        self.buffer += text
                        self.last_recv = time.monotonic()
                        self.lock.notify_all()
                    try:
                        self._transcript.write(text.decode("utf-8", "replace"))
                    except Exception:
                        pass
        except OSError:
            pass
        finally:
            with self.lock:
                self.closed = True
                self.lock.notify_all()

    def _write(self, line: str):
        # CircleMUD wants CRLF; an empty line means "just press enter".
        self.sock.sendall((line + "\r\n").encode("utf-8"))
        self._transcript.write(f"\n>>> {line!r}\n")

    def drain(self) -> str:
        with self.lock:
            out = self.buffer.decode("utf-8", "replace")
            self.buffer.clear()
            return out

    def read_until_quiet(self, quiet=0.4, timeout=10.0, require_new_after=None) -> str:
        """Return once `quiet` seconds pass with no new bytes, or `timeout`
        total elapses. This is format-agnostic — it doesn't depend on the
        exact prompt string, so it survives custom prompts and combat spam.

        `require_new_after` (a monotonic timestamp) guards against returning
        stale buffer: after sending a command we pass the send time here, so
        the quiet window only counts once the server's reply to THAT command
        has begun arriving. Without it, async text left in the buffer would be
        handed back as if it were the reply, lagging every command by one."""
        deadline = time.monotonic() + timeout
        with self.lock:
            while True:
                now = time.monotonic()
                if now >= deadline:
                    break
                fresh = self.last_recv is not None and (
                    require_new_after is None or self.last_recv >= require_new_after
                )
                if fresh and self.buffer and (now - self.last_recv) >= quiet:
                    break
                if self.closed:
                    break
                if fresh and self.buffer:
                    wait = min(quiet - (now - self.last_recv), deadline - now)
                else:
                    wait = deadline - now
                if wait > 0:
                    self.lock.wait(wait)
            out = self.buffer.decode("utf-8", "replace")
            self.buffer.clear()
            return out

    def read_until(self, pattern, timeout=15.0) -> str:
        rx = re.compile(pattern, re.IGNORECASE) if isinstance(pattern, str) else pattern
        deadline = time.monotonic() + timeout
        with self.lock:
            while True:
                text = self.buffer.decode("utf-8", "replace")
                m = rx.search(text)
                if m:
                    cut = m.end()
                    consumed = text[:cut].encode("utf-8")
                    del self.buffer[: len(consumed)]
                    return text[:cut]
                remaining = deadline - time.monotonic()
                if remaining <= 0 or self.closed:
                    raise TimeoutError(f"pattern {pattern!r} not seen in {timeout}s")
                self.lock.wait(remaining)

    # ---- login dance ----

    def login(self):
        """Walk the CircleMUD login flow for an EXISTING character, tolerating
        MOTD 'press return' pages and the numbered main menu."""
        self.read_until(r"By what name do you wish to be known.*\?", timeout=15)
        self._write(self.user)
        self.read_until(r"Password", timeout=15)
        self._write(self.password)

        # After the password we may see: a wrong-password bounce, an immediate
        # reconnect (already in world), one or more MOTD pages gated behind
        # "press RETURN", and finally a numbered menu. Pump until we're in.
        for _ in range(12):
            chunk = self.read_until_quiet(quiet=0.4, timeout=6)
            if re.search(r"Wrong password|invalid password", chunk, re.I):
                raise RuntimeError("login failed: wrong password")
            if re.search(r"Reconnecting", chunk, re.I):
                self.logged_in = True
                return
            if re.search(r"Make your choice|^\s*1\)\s*Enter the game", chunk, re.I | re.M):
                self._write("1")
                self.read_until_quiet(quiet=0.5, timeout=8)
                self.logged_in = True
                return
            if re.search(r"press return|\[ Return|hit RETURN|continue\]", chunk, re.I):
                self._write("")           # advance the MOTD pager
                continue
            if chunk.strip() == "":
                # Quiet with nothing new — nudge with a blank line in case a
                # prompt is waiting silently.
                self._write("")
        # Best effort: assume we made it in; a follow-up `look` will confirm.
        self.logged_in = True

    # ---- control server (talks to client subcommands) ----

    def serve(self):
        if os.path.exists(self.p["sock"]):
            os.unlink(self.p["sock"])
        srv = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        srv.bind(self.p["sock"])
        srv.listen(4)
        while not self.closed:
            try:
                conn, _ = srv.accept()
            except OSError:
                break
            try:
                self._handle(conn)
            finally:
                conn.close()
        try:
            srv.close()
            os.unlink(self.p["sock"])
        except OSError:
            pass

    def _handle(self, conn):
        data = b""
        while not data.endswith(b"\n"):
            part = conn.recv(65536)
            if not part:
                break
            data += part
        if not data:
            return
        try:
            req = json.loads(data.decode("utf-8"))
        except ValueError:
            conn.sendall(b'{"error":"bad request"}\n')
            return

        op = req.get("op")
        resp = {"ok": True}
        if op == "send":
            sent_at = time.monotonic()
            self._write(req.get("line", ""))
            resp["output"] = self.read_until_quiet(
                quiet=req.get("quiet", 0.4), timeout=req.get("timeout", 10),
                require_new_after=sent_at,
            )
        elif op == "read":
            resp["output"] = self.read_until_quiet(
                quiet=req.get("quiet", 0.3), timeout=req.get("timeout", 3)
            )
        elif op == "status":
            resp.update(
                alive=not self.closed,
                logged_in=self.logged_in,
                host=self.host,
                port=self.port,
                user=self.user,
            )
        elif op == "stop":
            resp["stopping"] = True
            conn.sendall((json.dumps(resp) + "\n").encode("utf-8"))
            self.closed = True
            try:
                self.sock.close()
            except OSError:
                pass
            return
        else:
            resp = {"ok": False, "error": f"unknown op {op!r}"}
        conn.sendall((json.dumps(resp) + "\n").encode("utf-8"))

    def run(self):
        with open(self.p["pid"], "w") as f:
            f.write(str(os.getpid()))
        try:
            self.connect()
            self.login()
            self.serve()
        finally:
            for key in ("pid", "sock"):
                try:
                    os.unlink(self.p[key])
                except OSError:
                    pass


# ---------------------------------------------------------------------------
# Client helpers
# ---------------------------------------------------------------------------

def daemon_alive(port):
    p = paths(port)
    if not os.path.exists(p["pid"]) or not os.path.exists(p["sock"]):
        return False
    try:
        with open(p["pid"]) as f:
            pid = int(f.read().strip())
        os.kill(pid, 0)         # signal 0 = existence check
        return True
    except (OSError, ValueError):
        return False


def request(port, payload, timeout=30):
    p = paths(port)
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    s.settimeout(timeout)
    s.connect(p["sock"])
    s.sendall((json.dumps(payload) + "\n").encode("utf-8"))
    data = b""
    while not data.endswith(b"\n"):
        part = s.recv(65536)
        if not part:
            break
        data += part
    s.close()
    return json.loads(data.decode("utf-8"))


# ---------------------------------------------------------------------------
# Subcommands
# ---------------------------------------------------------------------------

def cmd_start(args):
    if daemon_alive(args.port):
        print(f"daemon already running on port {args.port}")
        return 0
    # Re-exec ourselves in a detached daemon process so it outlives this call.
    import subprocess

    logf = open(paths(args.port)["log"], "a")
    env = dict(os.environ)
    argv = [
        sys.executable, os.path.abspath(__file__),
        "--host", args.host, "--port", str(args.port),
        "--user", args.user, "--password", args.password,
        "__daemon__",
    ]
    subprocess.Popen(
        argv, stdout=logf, stderr=logf, stdin=subprocess.DEVNULL,
        start_new_session=True, env=env,
    )
    # Wait for the daemon to come up and log in.
    for _ in range(60):
        if daemon_alive(args.port):
            try:
                st = request(args.port, {"op": "status"}, timeout=5)
                if st.get("logged_in"):
                    print(f"daemon up on port {args.port}, logged in as {args.user}")
                    return 0
            except OSError:
                pass
        time.sleep(0.5)
    print("daemon did not become ready; check the log:", paths(args.port)["log"],
          file=sys.stderr)
    return 1


def cmd_daemon(args):
    MudDaemon(args.host, args.port, args.user, args.password).run()
    return 0


def _need_daemon(port):
    if not daemon_alive(port):
        print("no daemon running — run `mud.py start` first", file=sys.stderr)
        sys.exit(2)


def cmd_send(args):
    _need_daemon(args.port)
    line = " ".join(args.command)
    resp = request(args.port, {"op": "send", "line": line,
                               "quiet": args.quiet, "timeout": args.timeout})
    sys.stdout.write(resp.get("output", ""))
    return 0


def cmd_read(args):
    _need_daemon(args.port)
    resp = request(args.port, {"op": "read", "quiet": args.quiet, "timeout": args.timeout})
    sys.stdout.write(resp.get("output", ""))
    return 0


def cmd_status(args):
    if not daemon_alive(args.port):
        print(json.dumps({"alive": False, "port": args.port}))
        return 0
    print(json.dumps(request(args.port, {"op": "status"})))
    return 0


def cmd_transcript(args):
    t = paths(args.port)["transcript"]
    if not os.path.exists(t):
        print("(no transcript yet)")
        return 0
    with open(t) as f:
        sys.stdout.write(f.read())
    return 0


def cmd_stop(args):
    if not daemon_alive(args.port):
        print("no daemon running")
        return 0
    try:
        request(args.port, {"op": "stop"}, timeout=5)
    except OSError:
        pass
    print("daemon stopped")
    return 0


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_parser():
    p = argparse.ArgumentParser(description="Persistent MUD session helper")
    p.add_argument("--host", default=DEFAULT_HOST)
    p.add_argument("--port", type=int, default=DEFAULT_PORT)
    p.add_argument("--user", default=DEFAULT_USER)
    p.add_argument("--password", default=DEFAULT_PASS)
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("start", help="spawn the session daemon and log in").set_defaults(fn=cmd_start)
    sub.add_parser("__daemon__").set_defaults(fn=cmd_daemon)  # internal

    s = sub.add_parser("send", help="send a command, print the reply")
    s.add_argument("command", nargs="+")
    s.add_argument("--quiet", type=float, default=0.4,
                   help="seconds of silence that mark end of reply")
    s.add_argument("--timeout", type=float, default=10)
    s.set_defaults(fn=cmd_send)

    r = sub.add_parser("read", help="drain async output without sending")
    r.add_argument("--quiet", type=float, default=0.3)
    r.add_argument("--timeout", type=float, default=3)
    r.set_defaults(fn=cmd_read)

    sub.add_parser("status", help="show daemon/login status").set_defaults(fn=cmd_status)
    sub.add_parser("transcript", help="print the full session log").set_defaults(fn=cmd_transcript)
    sub.add_parser("stop", help="shut the daemon down").set_defaults(fn=cmd_stop)
    return p


def main():
    args = build_parser().parse_args()
    sys.exit(args.fn(args))


if __name__ == "__main__":
    main()
