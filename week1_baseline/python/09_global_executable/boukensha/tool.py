class Tool:
    """A tool the agent is allowed to invoke.

    Ported from the Ruby ``Struct``. ``block`` is any callable that runs when
    the tool is called.
    """

    def __init__(self, name, description, parameters, block):
        self.name = name
        self.description = description
        self.parameters = parameters
        self.block = block

    def __str__(self):
        return (
            f"#<Tool name={self.name} "
            f"description={str(self.description)[:41]} "
            f"params={list(self.parameters.keys())}>"
        )

    def __repr__(self):
        return self.__str__()
