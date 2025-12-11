"""Configuration management for Agent Assistant."""
import os
import yaml
from pathlib import Path
from typing import Any, Optional
from dotenv import load_dotenv


class Config:
    """Singleton configuration manager."""

    _instance: Optional['Config'] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self._initialized = True
        self._load_env()
        self._load_yaml()

    def _load_env(self):
        """Load environment variables from .env file."""
        env_path = Path(__file__).parent.parent.parent / ".env"
        load_dotenv(env_path)

    def _load_yaml(self):
        """Load configuration from YAML file."""
        config_path = Path(__file__).parent.parent.parent / "config" / "config.yaml"

        if not config_path.exists():
            raise FileNotFoundError(f"Config file not found: {config_path}")

        with open(config_path, 'r') as f:
            self.config = yaml.safe_load(f)

    def get(self, key_path: str, default: Any = None) -> Any:
        """
        Get configuration value using dot notation.

        Args:
            key_path: Dot-separated path (e.g., 'llm.local.model')
            default: Default value if key not found

        Returns:
            Configuration value or default

        Example:
            >>> config = Config()
            >>> config.get('llm.local.model')
            'llama3.1:8b'
        """
        keys = key_path.split('.')
        value = self.config

        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return default

        return value

    def get_env(self, key: str, default: Any = None) -> Any:
        """
        Get environment variable.

        Args:
            key: Environment variable name
            default: Default value if not found

        Returns:
            Environment variable value or default
        """
        return os.getenv(key, default)

    def get_api_key(self, provider: str) -> Optional[str]:
        """
        Get API key for specific provider.

        Args:
            provider: Provider name ('openai', 'openrouter', 'moonshot', 'anthropic', 'google', 'groq', 'tavily')

        Returns:
            API key or None
        """
        key_mapping = {
            'openai': 'OPENAI_API_KEY',
            'openrouter': 'OPENROUTER_API_KEY',
            'moonshot': 'MOONSHOT_API_KEY',
            'anthropic': 'ANTHROPIC_API_KEY',
            'google': 'GOOGLE_API_KEY',
            'groq': 'GROQ_API_KEY',
            'tavily': 'TAVILY_API_KEY',
        }

        env_key = key_mapping.get(provider.lower())
        if not env_key:
            raise ValueError(f"Unknown provider: {provider}")

        return self.get_env(env_key)

    def get_llm_config(self, tier: str) -> dict:
        """
        Get LLM configuration for specific tier.

        Args:
            tier: 'local' or 'remote'

        Returns:
            LLM configuration dict
        """
        return self.get(f'llm.{tier}', {})

    def get_workspace_dir(self) -> Path:
        """
        Get agent workspace directory.

        Returns current working directory where the agent is run from.
        This allows the agent to work on the repository it's installed in.

        Returns:
            Path to current working directory
        """
        # Use current working directory as workspace
        # This allows the agent to work on the repo it's run from
        return Path.cwd()

    @property
    def monthly_budget(self) -> float:
        """Get monthly budget limit in USD."""
        return float(self.get('llm.routing.cost_limit_monthly', 50))

    @property
    def prefer_local(self) -> bool:
        """Whether to prefer local models when possible."""
        return bool(self.get('llm.routing.prefer_local', True))

    def get_available_remote_models(self) -> list:
        """
        Get list of available remote models.

        Returns:
            List of model dicts with id, name, and description
        """
        return self.get('llm.remote.available_models', [])

    def get_current_remote_model(self) -> str:
        """
        Get current active remote model ID.

        Returns:
            Model ID string
        """
        return self.get('llm.remote.model', 'google/gemini-2.5-pro-exp-03-25:free')

    def set_remote_model(self, model_id: str):
        """
        Set the active remote model.

        Args:
            model_id: Model ID to set as active

        Raises:
            ValueError: If model_id is not in available models
        """
        available = self.get_available_remote_models()
        available_ids = [m['id'] for m in available]

        if model_id not in available_ids:
            raise ValueError(f"Model {model_id} not in available models")

        # Update in-memory config
        self.config['llm']['remote']['model'] = model_id

        # Persist to file
        config_path = Path(__file__).parent.parent.parent / "config" / "config.yaml"
        with open(config_path, 'w') as f:
            yaml.dump(self.config, f, default_flow_style=False, sort_keys=False)

    def get_local_mode(self) -> str:
        """
        Get current local model mode (simplified - always returns 'default').

        Returns:
            Mode string (always "default" in simplified single-mode system)
        """
        return 'default'

    def set_local_mode(self, mode: str):
        """
        Set local model mode (no-op in simplified single-mode system).

        Args:
            mode: Mode to set (ignored)

        Note:
            This method is kept for backwards compatibility but does nothing
            in the simplified single-mode system.
        """
        # No-op: single-mode system doesn't use modes
        pass

    def reload(self):
        """Reload configuration from files."""
        self._load_env()
        self._load_yaml()

    def get_sticky_model_enabled(self) -> bool:
        """
        Check if sticky model behavior is enabled.

        Returns:
            True if sticky model is enabled
        """
        return bool(self.get('llm.routing.sticky_model', True))

    def get_last_successful_model(self, tier: str) -> Optional[str]:
        """
        Get the last successful model for a tier.

        Args:
            tier: 'local' or 'remote'

        Returns:
            Model ID or None
        """
        return self.get(f'llm.routing.last_successful_{tier}_model')

    def set_last_successful_model(self, tier: str, model_id: str):
        """
        Set the last successful model for a tier.

        Args:
            tier: 'local' or 'remote'
            model_id: Model ID that succeeded
        """
        config_key = f'last_successful_{tier}_model'

        # Ensure routing section exists
        if 'routing' not in self.config['llm']:
            self.config['llm']['routing'] = {}

        # Update in-memory config
        self.config['llm']['routing'][config_key] = model_id

        # Persist to file
        config_path = Path(__file__).parent.parent.parent / "config" / "config.yaml"
        with open(config_path, 'w') as f:
            yaml.dump(self.config, f, default_flow_style=False, sort_keys=False)

    def get_user_force_model(self) -> Optional[str]:
        """
        Get persisted user force_model preference.

        Returns:
            "local", "remote", or None (auto)
        """
        return self.config.get("llm", {}).get("routing", {}).get("user_force_model")

    def set_user_force_model(self, mode: Optional[str]) -> None:
        """
        Save user's force_model preference to config file.

        Args:
            mode: "local", "remote", or None (auto)

        Raises:
            ValueError: If mode is invalid
        """
        if mode not in [None, "local", "remote"]:
            raise ValueError(f"Invalid force_model mode: {mode}")

        # Ensure routing section exists
        if 'llm' not in self.config:
            self.config['llm'] = {}
        if 'routing' not in self.config['llm']:
            self.config['llm']['routing'] = {}

        # Update in-memory config
        self.config['llm']['routing']['user_force_model'] = mode

        # Persist to file
        config_path = Path(__file__).parent.parent.parent / "config" / "config.yaml"
        with open(config_path, 'w') as f:
            yaml.dump(self.config, f, default_flow_style=False, sort_keys=False)


# Global config instance
config = Config()
