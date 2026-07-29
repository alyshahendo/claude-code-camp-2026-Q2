from .errors import UnknownToolError
from .tool import Tool


class Registry:
    """Stores tools and dispatches calls to them.

    The agent never calls a tool directly. It emits a structured request (name
    and args); the Registry looks up the tool and runs it.
    """

    def __init__(self, context):
        self.context = context

    def tool(self, name, description, parameters=None, block=None):
        """Register a new tool on the context and return it."""
        registered = Tool(str(name), description, parameters or {}, block)
        self.context.register_tool(registered)
        return registered

    def dispatch(self, name, args=None):
        """Look up a tool by name and call it with the provided args."""
        registered = self.context.tools.get(str(name))
        if registered is None:
            raise UnknownToolError(f"No tool registered as '{name}'")
        # The API returns arguments as string-keyed JSON. Python kwargs are
        # strings too, so unpacking maps them straight onto the block's params.
        return registered.block(**{str(k): v for k, v in (args or {}).items()})
