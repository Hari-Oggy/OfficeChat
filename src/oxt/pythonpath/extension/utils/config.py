import json
import os
from pathlib import Path
from typing import Dict, Any

class ConfigManager:
    """Manages AI extension configuration and secure API keys."""
    
    def __init__(self):
        # Store in ~/.config/libreoffice_ai/config.json
        config_dir = Path.home() / ".config" / "libreoffice_ai"
        self.config_path = config_dir / "config.json"
        self._ensure_config_file(config_dir)
        self.config = self._load_config()

    def _ensure_config_file(self, config_dir: Path):
        """Creates the config directory and file with restricted permissions if they don't exist."""
        if not config_dir.exists():
            config_dir.mkdir(parents=True, exist_ok=True)
            # Try to restrict directory permissions
            try:
                config_dir.chmod(0o700)
            except Exception:
                pass
                
        if not self.config_path.exists():
            default_config = {
                "active_provider": "google",
                "providers": {
                    "openai": {
                        "api_key": "",
                        "model": "gpt-4o"
                    },
                    "google": {
                        "api_key": "",
                        "model": "gemini-1.5-pro"
                    },
                    "groq": {
                        "api_key": "",
                        "model": "llama3-70b-8192"
                    },
                    "openrouter": {
                        "api_key": "",
                        "model": "meta-llama/llama-3-8b-instruct:free"
                    },
                    "ollama": {
                        "api_key": "ollama",
                        "model": "llama3",
                        "base_url": "http://localhost:11434/v1"
                    }
                }
            }
            with open(self.config_path, "w") as f:
                json.dump(default_config, f, indent=4)
            # Try to restrict file permissions
            try:
                self.config_path.chmod(0o600)
            except Exception:
                pass

    def _load_config(self) -> Dict[str, Any]:
        try:
            with open(self.config_path, "r") as f:
                return json.load(f)
        except Exception:
            return {}

    def _save_config(self):
        try:
            with open(self.config_path, "w") as f:
                json.dump(self.config, f, indent=4)
        except Exception:
            pass

    def get_provider_config(self, provider_name: str) -> Dict[str, str]:
        """Returns the config for a specific provider."""
        return self.config.get("providers", {}).get(provider_name, {})

    def get_all_providers(self) -> list:
        return list(self.config.get("providers", {}).keys())

    def get_active_provider(self) -> str:
        return self.config.get("active_provider", "openai")

    def set_active_provider(self, provider_name: str):
        if provider_name in self.get_all_providers():
            self.config["active_provider"] = provider_name
            self._save_config()
