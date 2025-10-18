"""Configuration manager for Genesis CLI integrated with AI Studio."""

import os
import yaml
from pathlib import Path
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field, HttpUrl

from langflow.services.deps import get_settings_service


class AIStudioConfig(BaseModel):
    """AI Studio connection configuration."""

    url: HttpUrl = Field(
        default="http://localhost:7860",
        description="AI Studio URL"
    )
    api_key: Optional[str] = Field(
        default=None,
        description="API key for authentication"
    )


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

    def _load_from_environment(self, config_data: Dict[str, Any]):
        """Load configuration from environment variables."""
        # AI Studio configuration
        if url := os.getenv("AI_STUDIO_URL", os.getenv("LANGFLOW_URL")):
            if "ai_studio" not in config_data:
                config_data["ai_studio"] = {}
            config_data["ai_studio"]["url"] = url

        # API key from multiple possible environment variables
        api_key = (
            os.getenv("AI_STUDIO_API_KEY") or
            os.getenv("LANGFLOW_API_KEY") or
            os.getenv("GENESIS_API_KEY")
        )
        if api_key:
            if "ai_studio" not in config_data:
                config_data["ai_studio"] = {}
            config_data["ai_studio"]["api_key"] = api_key

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

        # Update values
        for key, value in kwargs.items():
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

        config_info = []
        config_info.append("Genesis CLI Configuration")
        config_info.append("=" * 30)
        config_info.append(f"AI Studio URL: {self.config.ai_studio.url}")
        config_info.append(f"API Key: {'[Set]' if self.config.ai_studio.api_key else '[Not Set]'}")
        config_info.append(f"Default Project: {self.config.default_project or '[None]'}")
        config_info.append(f"Default Folder: {self.config.default_folder or '[None]'}")
        config_info.append(f"Templates Path: {self.config.templates_path or '[Default]'}")
        config_info.append(f"Verbose Mode: {self.config.verbose}")
        config_info.append(f"Config File: {self.config_file}")
        config_info.append(f"Config Dir: {self.config_dir}")

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

    @property
    def api_key(self) -> Optional[str]:
        """Get API key."""
        return self.get_config().ai_studio.api_key