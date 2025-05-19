
from typing import Optional
from backend.api.chat.chat_model_base import BaseChatModel
from backend.api.chat.chat_models.openai import OpenAIChatModel
from backend.api.chat.chat_models.bedrock import BedrockChatModel

class ChatFactory:
    @staticmethod
    def create_chat_model(
        provider: str,
        model: str,
        temperature: float = 0,
        api_key: Optional[str] = None,
    ) -> BaseChatModel:
        """
        Creates an instance of a chat model based on the provider.

        Args:
            provider: The provider to use (e.g., "openai").
            model: The model identifier (e.g., "gpt-3.5-turbo").
            temperature: Sampling temperature.
            api_key: Optional API key (if not provided, will rely on environment variables).

        Returns:
            An instance of BaseChatModel.

        Raises:
            ValueError: If an unsupported provider is specified.
        """
        provider = provider.lower()
        if provider == "openai":
            return OpenAIChatModel(model=model, temperature=temperature, api_key=api_key)
        if provider == "bedrock":
            return BedrockChatModel(model=model, temperature=temperature)
        raise ValueError(f"Unsupported provider: {provider}")