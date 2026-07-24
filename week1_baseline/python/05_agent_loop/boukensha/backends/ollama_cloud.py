from .base import Base


class OllamaCloud(Base):
    """Serializes context into the Ollama Cloud ``/api/chat`` format."""

    BASE_URL = "https://ollama.com"
    MODELS = {
        "gemma4:31b-cloud": {
            "context_window": 256_000,
            "cost_per_million": {"input": None, "output": None},
            "usage_unit": "ollama_cloud_usage",
            "usage_level": "medium",
        },
        "minimax-m3:cloud": {
            "context_window": 512_000,
            "advertised_context_window": 1_000_000,
            "cost_per_million": {"input": None, "output": None},
            "usage_unit": "ollama_cloud_usage",
            "usage_level": "high",
        },
        "kimi-k2.5:cloud": {
            "context_window": 256_000,
            "cost_per_million": {"input": None, "output": None},
            "usage_unit": "ollama_cloud_usage",
            "usage_level": "high",
        },
    }

    def __init__(self, api_key, model):
        self._api_key = api_key
        self._configure_model(model)

    def to_messages(self, system, messages):
        conversation = [{"role": "system", "content": system}]
        for msg in messages:
            if msg.role == "tool_result":
                conversation.append(
                    {"role": "tool", "tool_name": msg.tool_use_id, "content": msg.content}
                )
            elif msg.role == "assistant":
                conversation.append(self._assistant_message(msg.content))
            else:
                conversation.append({"role": str(msg.role), "content": msg.content})
        return conversation

    def to_tools(self, tools):
        return [
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": {
                        "type": "object",
                        "properties": tool.parameters,
                        "required": [str(key) for key in tool.parameters.keys()],
                    },
                },
            }
            for tool in tools.values()
        ]

    def to_payload(self, context, max_output_tokens=1024, tools=None):
        return {
            "model": self.model,
            "stream": False,
            "messages": self.to_messages(context.system, context.messages),
            "tools": self.to_tools(context.tools) if tools is None else tools,
        }

    def headers(self):
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self._api_key}",
        }

    def url(self):
        return f"{self.BASE_URL}/api/chat"

    # Normalizes an Ollama /api/chat response into the common shape:
    #   {"stop_reason": "tool_use" | "end_turn",
    #    "content": [ {"type": "text", "text": ...}
    #               | {"type": "tool_use", "id": ..., "name": ..., "input": ...} ]}
    # Ollama does not assign call ids, so the function name is reused as the id
    # (Ollama also matches tool results back to a call by name).
    def parse_response(self, response):
        message = response.get("message") or {}
        tool_calls = message.get("tool_calls") or []

        content = []
        if message.get("content"):
            content.append({"type": "text", "text": message["content"]})

        for tool_call in tool_calls:
            function = tool_call.get("function") or {}
            content.append(
                {
                    "type": "tool_use",
                    "id": function.get("name"),
                    "name": function.get("name"),
                    "input": function.get("arguments") or {},
                }
            )

        return {
            "stop_reason": "end_turn" if not tool_calls else "tool_use",
            "content": content,
        }

    # ---------- private ---------------------------------------------------

    # Rebuilds an Ollama assistant message from normalized content blocks
    # (the inverse of parse_response).
    def _assistant_message(self, content):
        blocks = [{"type": "text", "text": content}] if isinstance(content, str) else content

        text_blocks = [block for block in blocks if block["type"] == "text"]
        tool_blocks = [block for block in blocks if block["type"] == "tool_use"]

        message = {
            "role": "assistant",
            "content": "".join(block["text"] for block in text_blocks),
        }
        if tool_blocks:
            message["tool_calls"] = [
                {"function": {"name": block["name"], "arguments": block["input"]}}
                for block in tool_blocks
            ]
        return message
