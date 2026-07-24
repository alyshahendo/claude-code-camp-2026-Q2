class UnknownToolError(Exception):
    """Raised when ``dispatch`` is called with a name that has no registered tool."""


class UnsupportedModelError(Exception):
    """Raised when a backend is initialized with a model it does not support."""


class ApiError(Exception):
    """Raised when an HTTP request to a backend API fails.

    A non-2xx response means something went wrong (bad API key, malformed
    payload, server error). The client surfaces this explicitly rather than
    returning a confusing ``None`` or partial response.
    """
