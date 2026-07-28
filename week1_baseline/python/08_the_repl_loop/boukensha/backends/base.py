from ..errors import UnsupportedModelError


class Base:
    """Shared backend contract for model validation and model metadata.

    Each concrete backend defines a ``MODELS`` table keyed by model name. A
    backend refuses to initialize with an unknown model, so ``settings.yaml``
    cannot silently select an unsupported or misspelled model.
    """

    MODELS = None

    @classmethod
    def models(cls):
        if cls.MODELS is None:
            raise NotImplementedError(f"{cls.__name__} must define MODELS")
        return cls.MODELS

    @classmethod
    def model_info_for(cls, model):
        return cls.models().get(str(model))

    @classmethod
    def validate_model(cls, model):
        model = str(model)
        if cls.model_info_for(model):
            return model

        supported = ", ".join(sorted(cls.models().keys()))
        raise UnsupportedModelError(
            f"{cls.__name__} does not support model {model!r}. Supported models: {supported}"
        )

    @property
    def model_info(self):
        return self._model_info

    @property
    def context_window(self):
        return self.model_info["context_window"]

    @property
    def input_token_cost_per_million(self):
        return self.model_info["cost_per_million"]["input"]

    @property
    def output_token_cost_per_million(self):
        return self.model_info["cost_per_million"]["output"]

    @property
    def usage_unit(self):
        return self.model_info["usage_unit"]

    @property
    def usage_level(self):
        return self.model_info.get("usage_level")

    def estimate_cost(self, input_tokens, output_tokens):
        input_cost = self.input_token_cost_per_million
        output_cost = self.output_token_cost_per_million
        if input_cost is None or output_cost is None:
            return None

        return (input_tokens * input_cost + output_tokens * output_cost) / 1_000_000

    # ---------- private ---------------------------------------------------

    def _configure_model(self, model):
        self.model = self.validate_model(model)
        self._model_info = self.model_info_for(self.model)
