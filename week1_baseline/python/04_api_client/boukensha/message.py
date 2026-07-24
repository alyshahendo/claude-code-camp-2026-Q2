class Message:
    """A single unit of conversation between the user and the agent.

    Ported from the Ruby ``Struct``. ``tool_use_id`` links a tool result back to
    the specific tool call that requested it.
    """

    def __init__(self, role, content, tool_use_id=None):
        self.role = role
        self.content = content
        self.tool_use_id = tool_use_id

    def __str__(self):
        id_tag = f" [{self.tool_use_id}]" if self.tool_use_id else ""
        return f"#<Message role={self.role}{id_tag} content={str(self.content)[:61]}...>"

    def __repr__(self):
        return self.__str__()
