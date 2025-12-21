from .mock import MockProvider

PROVIDERS = {
    "general": MockProvider(),
    "reasoning": MockProvider(),
    "coding": MockProvider(),
    "emotional": MockProvider()
}

def get_provider(task_type: str):
    return PROVIDERS.get(task_type, PROVIDERS["general"])