class UnknownToolError(Exception):
    """Raised when ``dispatch`` is called with a name that has no registered tool."""


class UnsupportedModelError(Exception):
    """Raised when a backend is initialized with a model it does not support."""
