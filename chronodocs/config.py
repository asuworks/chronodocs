from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml


class ConfigError(Exception):
    """Custom exception for configuration-related errors."""

    pass


class Config:
    """
    Manages the configuration for ChronoDocs, loading from a YAML file.
    """

    def __init__(self, config_path: Path):
        self._config_path = config_path
        self._config = self._load_config()

    def _load_config(self) -> Dict[str, Any]:
        """Loads the configuration from the YAML file."""
        if not self._config_path.is_file():
            raise ConfigError(f"Configuration file not found: {self._config_path}")
        try:
            with open(self._config_path, "r") as f:
                config = yaml.safe_load(f)
        except yaml.YAMLError as e:
            raise ConfigError(
                f"Invalid YAML in configuration file {self._config_path}: {e}"
            )
        except Exception as e:
            raise ConfigError(
                f"Error reading configuration file {self._config_path}: {e}"
            )
        return config or {}

    def get(self, key: str, default: Any = None) -> Any:
        """Retrieves a configuration value."""
        return self._config.get(key, default)

    @property
    def phase_dir_template(self) -> str:
        return self.get("phase_dir_template", ".devcontext/progress/{phase}")

    @property
    def watch_paths(self) -> List[str]:
        return self.get("watch_paths", [])

    @property
    def ignore_patterns(self) -> List[str]:
        return self.get("ignore_patterns", [])

    @property
    def debounce_phase(self) -> int:
        debounce = self.get("debounce", {})
        return debounce.get("phase", 2000)

    @property
    def debounce_root(self) -> int:
        debounce = self.get("debounce", {})
        return debounce.get("root", 3000)

    @property
    def min_interval_phase(self) -> int:
        debounce = self.get("debounce", {})
        return debounce.get("min_interval_phase", 8000)

    @property
    def min_interval_root(self) -> int:
        debounce = self.get("debounce", {})
        return debounce.get("min_interval_root", 8000)

    @property
    def make_command(self) -> Optional[str]:
        return self.get("make_command")

    @property
    def report_config(self) -> Dict[str, Any]:
        return self.get("report", {})

    @property
    def report_extensions(self) -> List[str]:
        report = self.get("report", {})
        return report.get("extensions", [".md", ".py", ".txt"])

    @property
    def report_group_by(self) -> str:
        report = self.get("report", {})
        return report.get("group_by", "updated_day")

    @property
    def report_sort_by(self) -> str:
        report = self.get("report", {})
        return report.get("sort_by", "updated_desc")

    @property
    def logging_config(self) -> Dict[str, str]:
        return self.get("logging", {"level": "INFO", "format": "text"})


def get_config(repo_root: Path = Path(".")) -> Config:
    """
    Factory function to get the configuration.
    """
    config_path = repo_root / ".chronodocs.yml"
    return Config(config_path)
