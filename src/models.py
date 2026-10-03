from langchain.chat_models import init_chat_model
from pydantic import SecretStr


def get_model(config, timeout=45, *, openai_api_key=None):
    """Explicit credentials belong to this client, never the shared environment."""
    credentials = {}
    if openai_api_key is not None:
        if config.provider != "openai":
            raise ValueError("A personal OpenAI key requires OpenAI models.")
        key = openai_api_key.strip()
        if not key:
            raise ValueError("Enter an OpenAI API key.")
        credentials["api_key"] = SecretStr(key)
    return init_chat_model(
        model=config.name, model_provider=config.provider,
        temperature=config.temperature, timeout=timeout, max_retries=0,
        **credentials,
    )
