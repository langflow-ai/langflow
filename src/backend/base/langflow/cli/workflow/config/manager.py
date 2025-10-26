"""Configuration manager for Genesis CLI integrated with AI Studio."""

import os
import yaml
from pathlib import Path
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field, HttpUrl
from dotenv import load_dotenv

from langflow.services.deps import get_settings_service


class AIStudioConfig(BaseModel):
    """AI Studio connection configuration."""

    url: HttpUrl = Field(
        default="http://localhost:7860",
        description="AI Studio URL"
    )
    # Note: API key is no longer stored in config file, read from environment variables


class GenesisConfig(BaseModel):
    """Genesis CLI configuration."""

    ai_studio: AIStudioConfig = Field(default_factory=AIStudioConfig)
    default_project: Optional[str] = Field(None, description="Default project for flows")
    default_folder: Optional[str] = Field(None, description="Default folder for flows")
    templates_path: Optional[Path] = Field(None, description="Custom templates directory")
    verbose: bool = Field(False, description="Enable verbose output")


class ConfigManager:
    """Manages Genesis CLI configuration integrated with AI Studio."""

    def __init__(self):
        self.config_dir = Path.home() / ".ai-studio"
        self.config_file = self.config_dir / "genesis-config.yaml"
        self.config: Optional[GenesisConfig] = None
        self._load_config()

    def _ensure_config_dir(self):
        """Ensure configuration directory exists."""
        self.config_dir.mkdir(exist_ok=True)

    def _load_config(self):
        """Load configuration from file and environment."""
        config_data = {}

        # Load .env files before processing config
        self._load_dotenv_files()

        # Load from file if exists
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r') as f:
                    file_config = yaml.safe_load(f) or {}
                    config_data.update(file_config)
            except Exception as e:
                # File exists but can't be loaded, use defaults
                pass

        # Override with environment variables
        self._load_from_environment(config_data)

        # Try to get AI Studio URL from running service
        self._load_from_service(config_data)

        # Create config object
        self.config = GenesisConfig(**config_data)

    def _load_dotenv_files(self):
        """Load .env files in priority order."""
        # Priority order for .env files:
        # 1. Current directory .env
        # 2. Project root .env (go up directories to find)
        # 3. Home directory .env

        dotenv_paths = [
            Path.cwd() / ".env",  # Current directory
            self._find_project_root() / ".env",  # Project root
            Path.home() / ".env"  # Home directory
        ]

        for env_path in dotenv_paths:
            if env_path.exists():
                load_dotenv(env_path, override=False)  # Don't override already set variables

    def _find_project_root(self) -> Path:
        """Find project root by looking for common markers."""
        current = Path.cwd()
        markers = [".git", "pyproject.toml", "setup.py", "requirements.txt"]

        # Go up directories to find project root
        for parent in [current] + list(current.parents):
            if any((parent / marker).exists() for marker in markers):
                return parent

        # Fallback to current directory
        return current

    def _load_from_environment(self, config_data: Dict[str, Any]):
        """Load configuration from environment variables."""
        # AI Studio configuration
        if url := os.getenv("AI_STUDIO_URL", os.getenv("LANGFLOW_URL")):
            if "ai_studio" not in config_data:
                config_data["ai_studio"] = {}
            config_data["ai_studio"]["url"] = url

        # Note: API key is no longer loaded here - it's accessed directly via get_api_key()

        # Genesis-specific settings
        if project := os.getenv("GENESIS_DEFAULT_PROJECT"):
            config_data["default_project"] = project

        if folder := os.getenv("GENESIS_DEFAULT_FOLDER"):
            config_data["default_folder"] = folder

        if templates_path := os.getenv("GENESIS_TEMPLATES_PATH"):
            config_data["templates_path"] = templates_path

        if verbose := os.getenv("GENESIS_VERBOSE"):
            config_data["verbose"] = verbose.lower() == "true"

    def _load_from_service(self, config_data: Dict[str, Any]):
        """Load configuration from running AI Studio service."""
        try:
            settings_service = get_settings_service()
            settings = settings_service.settings

            # Use AI Studio's host and port if available
            if hasattr(settings, 'host') and hasattr(settings, 'port'):
                host = getattr(settings, 'host', 'localhost')
                port = getattr(settings, 'port', 7860)

                # Don't override if already set from environment/file
                if "ai_studio" not in config_data:
                    config_data["ai_studio"] = {}
                if "url" not in config_data.get("ai_studio", {}):
                    # Use localhost for internal access
                    if host in ['0.0.0.0', '127.0.0.1']:
                        host = 'localhost'
                    config_data["ai_studio"]["url"] = f"http://{host}:{port}"

        except Exception:
            # Service not available, use defaults
            pass

    def save_config(self):
        """Save current configuration to file."""
        self._ensure_config_dir()

        if self.config:
            config_dict = self.config.model_dump(exclude_none=True)

            # Ensure API key is not saved to config file
            if "ai_studio" in config_dict and "api_key" in config_dict["ai_studio"]:
                del config_dict["ai_studio"]["api_key"]

            with open(self.config_file, 'w') as f:
                yaml.dump(config_dict, f, default_flow_style=False, sort_keys=False)

    def get_config(self) -> GenesisConfig:
        """Get current configuration."""
        if self.config is None:
            self._load_config()
        return self.config

    def update_config(self, **kwargs):
        """Update configuration values."""
        if self.config is None:
            self._load_config()

        # Filter out API key updates
        filtered_kwargs = {}
        for key, value in kwargs.items():
            if key in ['ai_studio_api_key', 'api_key']:
                # Don't update API key in config - it should be set via environment
                continue
            filtered_kwargs[key] = value

        # Update values
        for key, value in filtered_kwargs.items():
            if hasattr(self.config, key):
                setattr(self.config, key, value)
            elif key.startswith('ai_studio_'):
                # Handle ai_studio nested values
                ai_studio_key = key.replace('ai_studio_', '')
                if hasattr(self.config.ai_studio, ai_studio_key):
                    setattr(self.config.ai_studio, ai_studio_key, value)

        # Save updated config
        self.save_config()

    def show_config(self) -> str:
        """Return formatted configuration display."""
        if self.config is None:
            self._load_config()

        # Get API key info
        api_key = self.get_api_key()
        api_key_source = self.get_api_key_source()
        api_key_display = f"[{api_key_source}]" if api_key else "[Not Set]"

        config_info = []
        config_info.append("Genesis CLI Configuration")
        config_info.append("=" * 30)
        config_info.append(f"AI Studio URL: {self.config.ai_studio.url}")
        config_info.append(f"API Key: {api_key_display}")
        config_info.append(f"Default Project: {self.config.default_project or '[None]'}")
        config_info.append(f"Default Folder: {self.config.default_folder or '[None]'}")
        config_info.append(f"Templates Path: {self.config.templates_path or '[Default]'}")
        config_info.append(f"Verbose Mode: {self.config.verbose}")
        config_info.append(f"Config File: {self.config_file}")
        config_info.append(f"Config Dir: {self.config_dir}")

        if not api_key:
            config_info.append("")
            config_info.append("To set API key, use environment variable:")
            config_info.append("  export AI_STUDIO_API_KEY=your-api-key")
            config_info.append("Or add to .env file:")
            config_info.append("  AI_STUDIO_API_KEY=your-api-key")

        return "\n".join(config_info)

    def import_genesis_agent_config(self) -> bool:
        """Import configuration from existing genesis-agent-cli."""
        # Look for genesis-agent-cli config
        potential_paths = [
            Path.home() / ".genesis-agent.yaml",
            Path.cwd() / ".genesis-agent.yaml",
            Path.cwd() / ".env"
        ]

        imported = False

        for config_path in potential_paths:
            if config_path.exists():
                try:
                    if config_path.suffix == '.yaml':
                        with open(config_path, 'r') as f:
                            old_config = yaml.safe_load(f) or {}

                        # Map old config to new format
                        if 'genesis_studio' in old_config:
                            old_studio_config = old_config['genesis_studio']
                            self.update_config(
                                ai_studio_url=old_studio_config.get('url'),
                                ai_studio_api_key=old_studio_config.get('api_key')
                            )
                            imported = True

                    elif config_path.name == '.env':
                        # Parse .env file
                        with open(config_path, 'r') as f:
                            for line in f:
                                line = line.strip()
                                if '=' in line and not line.startswith('#'):
                                    key, value = line.split('=', 1)
                                    key = key.strip()
                                    value = value.strip().strip('"\'')

                                    if key == 'GENESIS_STUDIO_URL':
                                        self.update_config(ai_studio_url=value)
                                        imported = True
                                    elif key in ['GENESIS_STUDIO_API_KEY', 'GENESIS_API_KEY']:
                                        self.update_config(ai_studio_api_key=value)
                                        imported = True

                except Exception:
                    continue

        return imported

    @property
    def ai_studio_url(self) -> str:
        """Get AI Studio URL as string."""
        return str(self.get_config().ai_studio.url)

    def get_api_key(self) -> Optional[str]:
        """Get API key from environment variables with priority order."""
        # Priority order:
        # 1. AI_STUDIO_API_KEY environment variable
        # 2. LANGFLOW_API_KEY environment variable
        # 3. GENESIS_API_KEY environment variable
        return (
            os.getenv("AI_STUDIO_API_KEY") or
            os.getenv("LANGFLOW_API_KEY") or
            os.getenv("GENESIS_API_KEY")
        )

    def get_api_key_source(self) -> Optional[str]:
        """Get the source of the API key for display purposes."""
        if os.getenv("AI_STUDIO_API_KEY"):
            return "From AI_STUDIO_API_KEY"
        elif os.getenv("LANGFLOW_API_KEY"):
            return "From LANGFLOW_API_KEY"
        elif os.getenv("GENESIS_API_KEY"):
            return "From GENESIS_API_KEY"
        return None

    @property
    def api_key(self) -> Optional[str]:
        """Get API key - backward compatibility property."""
        return self.get_api_key()