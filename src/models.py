from langchain.chat_models import init_chat_model


def get_model(config, timeout=45):
    """Provider integration packages are optional except for the default OpenAI pair."""
    return init_chat_model(
        model=config.name, model_provider=config.provider,
        temperature=config.temperature, timeout=timeout, max_retries=0,
    )
