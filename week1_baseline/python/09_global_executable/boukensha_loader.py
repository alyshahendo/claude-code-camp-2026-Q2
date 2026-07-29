"""Resolve which step's ``boukensha`` package to load, then boot the REPL.

This is the Python analog of the Ruby ``bin/boukensha`` + ``boukensha_loader.rb``:
a console-script entry point (declared in ``pyproject.toml`` under
``[project.scripts]``) that picks a lib, imports it, and starts the interactive
REPL. It lives outside the ``boukensha`` package on purpose, because its whole
job is to decide *which* ``boukensha`` to import.

Resolution order:
  1. ``BOUKENSHA_PATH`` environment variable (selects which step to load)
  2. ``~/.boukensharc`` (a file containing a single path)
  3. The ``boukensha`` package bundled with this install (the latest release)

The config directory (settings.yaml, .env, system.md) is separate and resolved
by ``Config``: set ``BOUKENSHA_DIR`` to override it.
"""

import os
import sys


def _step_with_package(path):
    """Return the absolute step dir if it contains ``boukensha/__init__.py``."""
    step_dir = os.path.abspath(os.path.expanduser(path))
    package = os.path.join(step_dir, "boukensha", "__init__.py")
    return step_dir if os.path.exists(package) else None


def resolve():
    """Return a step directory to prepend to ``sys.path``, or ``None`` for the
    bundled package."""
    # 1. Env var wins.
    env_path = os.environ.get("BOUKENSHA_PATH")
    if env_path:
        step_dir = _step_with_package(env_path)
        if step_dir:
            return step_dir
        sys.exit(
            "boukensha: BOUKENSHA_PATH is set but no boukensha/__init__.py found at:\n"
            f"       {os.path.abspath(os.path.expanduser(env_path))}\n"
            "       Make sure BOUKENSHA_PATH points to a step folder, e.g.:\n"
            "       BOUKENSHA_PATH=~/Sites/boukensha/08_the_repl_loop boukensha"
        )

    # 2. ~/.boukensharc
    rc = os.path.expanduser("~/.boukensharc")
    if os.path.exists(rc):
        with open(rc) as handle:
            rc_path = handle.read().strip()
        if rc_path:
            step_dir = _step_with_package(rc_path)
            if step_dir:
                return step_dir
            sys.exit(
                f"boukensha: ~/.boukensharc points to {rc_path}\n"
                "       but no boukensha/__init__.py was found there.\n"
                "       Update ~/.boukensharc or remove it to use the bundled default."
            )

    # 3. Bundled default.
    return None


def main():
    step_dir = resolve()
    if step_dir is not None:
        sys.path.insert(0, step_dir)

    import boukensha

    loaded_from = os.path.dirname(os.path.dirname(os.path.abspath(boukensha.__file__)))
    if os.environ.get("BOUKENSHA_DEBUG"):
        print(f"[boukensha] loading from: {loaded_from}")

    if not hasattr(boukensha, "repl"):
        sys.exit(
            f"boukensha: the boukensha at {loaded_from}\n"
            "       does not support the interactive REPL (added in step 8).\n"
            "       Point BOUKENSHA_PATH at step 8 or later."
        )

    boukensha.repl()


if __name__ == "__main__":
    main()
