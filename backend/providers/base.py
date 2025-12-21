class LLMProvider:
    name = "base"

    def chat(self, system: str, messages: list) -> str:
        raise NotImplementedError