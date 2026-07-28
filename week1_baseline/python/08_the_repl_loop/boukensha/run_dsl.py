class RunDSL:
    """The object handed to a ``boukensha.run`` block.

    It exposes only ``tool``, keeping the DSL surface intentionally small and
    preventing callers from reaching internal state. Ruby uses
    ``instance_eval`` so ``self`` inside the block becomes the ``RunDSL``; Python
    has no equivalent, so ``run`` calls the block with the ``RunDSL`` instance as
    its argument instead.
    """

    def __init__(self, registry):
        self._registry = registry

    def tool(self, name, description, parameters=None, block=None):
        return self._registry.tool(
            name, description=description, parameters=parameters, block=block
        )
