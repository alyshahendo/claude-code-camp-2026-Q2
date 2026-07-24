class PromptBuilder:
    """Serializes a ``Context`` into the exact format each API expects.

    The builder does not call any API. It delegates serialization to whichever
    backend it is given, so the same context can be prepared for Anthropic,
    OpenAI, Gemini, or Ollama without touching the rest of the harness.
    """

    def __init__(self, context, backend):
        self._context = context
        self._backend = backend

    def to_messages(self):
        return self._backend.to_messages(self._context.messages)

    def to_tools(self):
        return self._backend.to_tools(self._context.tools)

    def to_api_payload(self, max_output_tokens=1024, tools=None):
        return self._backend.to_payload(
            self._context, max_output_tokens=max_output_tokens, tools=tools
        )

    def parse_response(self, response):
        return self._backend.parse_response(response)

    def headers(self):
        return self._backend.headers()

    def url(self):
        return self._backend.url()
