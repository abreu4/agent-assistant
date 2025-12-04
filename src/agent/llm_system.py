"""Hybrid LLM system managing local and remote models."""
import asyncio
import random
from typing import Literal, Optional
from langchain_ollama import ChatOllama
from langchain_openai import ChatOpenAI
from langchain_core.language_models import BaseChatModel

from ..utils.config import config
from ..utils.logging import get_logger

logger = get_logger("llm_system")

ModelTier = Literal["local", "remote"]


class HybridLLMSystem:
    """Manages hybrid local + remote LLM architecture."""

    def __init__(self):
        """Initialize LLM system with local and remote models."""
        self._local_model: Optional[BaseChatModel] = None
        self._remote_model: Optional[BaseChatModel] = None
        self._classifier_model: Optional[BaseChatModel] = None
        self._current_local_model: Optional[str] = None  # Track current local model

        self._setup_models()

    def _setup_models(self):
        """Set up local and remote models based on configuration."""
        # Local model setup
        local_config = config.get_llm_config('local')
        if local_config:
            default_model = local_config.get('model', 'llama3.1:8b')
            logger.info(f"Setting up local model: {default_model}")

            # Track current model
            self._current_local_model = default_model

            # Main local model with fallback
            self._local_model = ChatOllama(
                model=default_model,
                temperature=local_config.get('temperature', 0.7),
                base_url=local_config.get('base_url', 'http://localhost:11434')
            ).with_fallbacks([
                ChatOllama(
                    model=local_config.get('fallback_model', 'mistral:7b'),
                    base_url=local_config.get('base_url', 'http://localhost:11434')
                )
            ])

            # Fast classifier model
            self._classifier_model = ChatOllama(
                model=local_config.get('classifier_model', 'llama3.2:3b'),
                temperature=0,
                base_url=local_config.get('base_url', 'http://localhost:11434')
            )

        # Remote model setup
        remote_config = config.get_llm_config('remote')
        if remote_config:
            self._setup_remote_model(remote_config)

    def _get_model_provider(self, model_id: str) -> str:
        """
        Determine the provider for a given model ID.

        Args:
            model_id: Model ID to check

        Returns:
            Provider name ('openrouter', 'moonshot', 'anthropic', 'google', 'groq')
        """
        remote_config = config.get_llm_config('remote')
        available_models = remote_config.get('available_models', [])

        # Check if model has explicit provider field
        for model in available_models:
            if model['id'] == model_id:
                return model.get('provider', 'openrouter')

        # Default to openrouter for models without explicit provider
        return 'openrouter'

    def _setup_remote_model(self, remote_config: dict):
        """
        Set up remote model with multi-provider support.

        Args:
            remote_config: Remote configuration dict
        """
        model_id = remote_config.get('model', 'google/gemini-2.5-pro-exp-03-25:free')
        provider = self._get_model_provider(model_id)

        logger.info(f"Setting up remote model: {model_id} via {provider}")

        # Try to get API key for the provider
        api_key = config.get_api_key(provider)

        # If no API key and provider is not openrouter, try openrouter as fallback
        if not api_key and provider != 'openrouter':
            logger.warning(f"No API key for {provider}, trying OpenRouter as fallback")
            openrouter_key = config.get_api_key('openrouter')
            if openrouter_key:
                provider = 'openrouter'
                api_key = openrouter_key
                logger.info(f"Using OpenRouter as fallback provider")

        # If still no API key, log warning but continue (will fail at runtime if used)
        if not api_key:
            logger.warning(f"No API key found for {provider}, remote models will not work without API key")
            logger.warning(f"Remote functionality will fall back to local models")
            api_key = "EMPTY"  # Placeholder

        # Determine base URL based on provider
        base_url_mapping = {
            'openrouter': remote_config.get('openrouter_base', 'https://openrouter.ai/api/v1'),
            'moonshot': remote_config.get('moonshot_base', 'https://api.moonshot.cn/v1'),
            'anthropic': remote_config.get('anthropic_base', 'https://api.anthropic.com'),
            'google': remote_config.get('google_base', 'https://generativelanguage.googleapis.com/v1beta'),
            'groq': remote_config.get('groq_base', 'https://api.groq.com/openai/v1'),
        }

        base_url = base_url_mapping.get(provider)

        # Create the model based on provider type
        if provider == 'anthropic':
            # Use anthropic-specific client
            try:
                from langchain_anthropic import ChatAnthropic
                self._remote_model = ChatAnthropic(
                    model=model_id,
                    temperature=remote_config.get('temperature', 0.6),
                    max_tokens=remote_config.get('max_tokens', 4096),
                    anthropic_api_key=api_key
                )
                logger.info("Using Anthropic native client")
            except ImportError:
                logger.warning("langchain_anthropic not installed, falling back to OpenAI-compatible interface")
                self._remote_model = ChatOpenAI(
                    model=model_id,
                    temperature=remote_config.get('temperature', 0.6),
                    max_tokens=remote_config.get('max_tokens', 4096),
                    openai_api_key=api_key,
                    openai_api_base=base_url
                )
        elif provider == 'google':
            # Use google-specific client
            try:
                from langchain_google_genai import ChatGoogleGenerativeAI
                self._remote_model = ChatGoogleGenerativeAI(
                    model=model_id,
                    temperature=remote_config.get('temperature', 0.6),
                    max_output_tokens=remote_config.get('max_tokens', 4096),
                    google_api_key=api_key
                )
                logger.info("Using Google AI native client")
            except ImportError:
                logger.warning("langchain_google_genai not installed, using OpenAI-compatible interface")
                self._remote_model = ChatOpenAI(
                    model=model_id,
                    temperature=remote_config.get('temperature', 0.6),
                    max_tokens=remote_config.get('max_tokens', 4096),
                    openai_api_key=api_key,
                    openai_api_base=base_url
                )
        else:
            # OpenRouter, Moonshot, Groq all use OpenAI-compatible interface
            self._remote_model = ChatOpenAI(
                model=model_id,
                temperature=remote_config.get('temperature', 0.6),
                max_tokens=remote_config.get('max_tokens', 4096),
                openai_api_key=api_key,
                openai_api_base=base_url
            )

    def _select_random_local_model(self) -> str:
        """
        Select a random local model from available models based on current mode.

        Returns:
            Model ID to use
        """
        local_config = config.get_llm_config('local')
        random_selection = local_config.get('random_selection', False)

        if not random_selection:
            # Return default model
            return local_config.get('model', 'llama3.1:8b')

        # Get current mode (default or code)
        mode = local_config.get('mode', 'default')

        # Get available models for current mode
        all_models = local_config.get('available_models', {})

        if isinstance(all_models, dict):
            # New format with modes
            available_models = all_models.get(mode, all_models.get('default', []))
        else:
            # Old format (list) - use directly
            available_models = all_models

        if not available_models:
            return local_config.get('model', 'llama3.1:8b')

        # Select random model
        selected = random.choice(available_models)
        logger.debug(f"Randomly selected local model ({mode} mode): {selected['name']}")
        return selected['id']

    def _create_local_model(self, model_id: str) -> BaseChatModel:
        """
        Create a local model instance.

        Args:
            model_id: Model ID to create

        Returns:
            ChatOllama instance
        """
        local_config = config.get_llm_config('local')
        return ChatOllama(
            model=model_id,
            temperature=local_config.get('temperature', 0.7),
            base_url=local_config.get('base_url', 'http://localhost:11434')
        )

    def get_model(self, tier: ModelTier) -> BaseChatModel:
        """
        Get model for specific tier.

        Args:
            tier: 'local' or 'remote'

        Returns:
            Language model instance

        Raises:
            ValueError: If model not configured
        """
        if tier == "local":
            if not self._local_model:
                raise ValueError("Local model not configured")

            # Check if we should randomly select a different model
            local_config = config.get_llm_config('local')
            if local_config.get('random_selection', False):
                # Select random model for this request
                new_model_id = self._select_random_local_model()

                # Only recreate if different from current
                if new_model_id != self._current_local_model:
                    self._current_local_model = new_model_id
                    self._local_model = self._create_local_model(new_model_id)
                    logger.info(f"🎲 Switched to local model: {new_model_id}")

            return self._local_model
        elif tier == "remote":
            if not self._remote_model:
                raise ValueError("Remote model not configured. Check API key in .env")
            return self._remote_model
        else:
            raise ValueError(f"Unknown tier: {tier}")

    def get_classifier(self) -> BaseChatModel:
        """
        Get fast classifier model for routing.

        Returns:
            Classifier model instance
        """
        if not self._classifier_model:
            logger.warning("Classifier not configured, using main local model")
            return self._local_model or self._remote_model

        return self._classifier_model

    async def warmup(self):
        """Warm up local models on startup to reduce first-request latency."""
        if not self._local_model:
            logger.debug("No local models to warm up")
            return

        logger.debug("Warming up local models...")
        warmup_prompt = "Hello"

        try:
            # Warm up main local model
            tasks = [self._local_model.ainvoke(warmup_prompt)]

            # Warm up classifier if different
            if self._classifier_model:
                tasks.append(self._classifier_model.ainvoke(warmup_prompt))

            await asyncio.gather(*tasks, return_exceptions=True)
            logger.debug("Local models warmed up successfully")

        except Exception as e:
            logger.warning(f"Failed to warm up models: {e}")

    def is_local_available(self) -> bool:
        """Check if local model is available."""
        return self._local_model is not None

    def is_remote_available(self) -> bool:
        """Check if remote model is available."""
        return self._remote_model is not None

    async def test_connection(self, tier: ModelTier) -> bool:
        """
        Test connection to model.

        Args:
            tier: Model tier to test

        Returns:
            True if connection successful
        """
        try:
            model = self.get_model(tier)
            response = await model.ainvoke("test")
            logger.info(f"{tier} model connection test successful")
            return True
        except Exception as e:
            logger.error(f"{tier} model connection test failed: {e}")
            return False

    def reload_remote_model(self):
        """Reload remote model with current configuration."""
        logger.info("Reloading remote model configuration")

        # Reload config first
        config.reload()

        # Re-setup remote model using the new multi-provider setup
        remote_config = config.get_llm_config('remote')
        if remote_config:
            self._setup_remote_model(remote_config)
            logger.info("Remote model reloaded successfully")

    def get_available_remote_models(self) -> list:
        """
        Get list of available remote models from config.

        Returns:
            List of model dicts
        """
        return config.get_available_remote_models()

    def get_current_remote_model(self) -> str:
        """
        Get current active remote model ID.

        Returns:
            Model ID string
        """
        return config.get_current_remote_model()

    def switch_remote_model(self, model_id: str):
        """
        Switch to a different remote model.

        Args:
            model_id: Model ID to switch to

        Raises:
            ValueError: If model_id is not available
        """
        config.set_remote_model(model_id)
        self.reload_remote_model()
