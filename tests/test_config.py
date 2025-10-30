import pytest
from pathlib import Path
import yaml

from chronodocs.config import Config

@pytest.fixture
def temp_config_file(tmp_path: Path) -> Path:
    config_data = {
        "phase_dir_template": ".test/{phase}",
        "watch_paths": ["src/"],
        "ignore_patterns": [".git/"],
        "debounce": {"phase": 1500, "root": 2500},
        "make_command": "echo 'hello'",
    }
    config_path = tmp_path / "config.yml"
    with open(config_path, 'w') as f:
        yaml.dump(config_data, f)
    return config_path

def test_load_config_success(temp_config_file: Path):
    """Test that a valid config file is loaded correctly."""
    config = Config(temp_config_file)
    assert config.phase_dir_template == ".test/{phase}"
    assert config.watch_paths == ["src/"]
    assert config.ignore_patterns == [".git/"]
    assert config.debounce_phase == 1500
    assert config.debounce_root == 2500
    assert config.make_command == "echo 'hello'"

@pytest.fixture
def empty_config_file(tmp_path: Path) -> Path:
    config_path = tmp_path / "empty_config.yml"
    config_path.touch()
    return config_path

def test_load_config_not_found():
    """Test that a FileNotFoundError is raised if the config file doesn't exist."""
    with pytest.raises(FileNotFoundError):
        Config(Path("non_existent_config.yml"))

def test_config_defaults(empty_config_file: Path):
    """Test that default values are returned for missing keys."""
    config = Config(empty_config_file)

    assert config.phase_dir_template == ".devcontext/progress/{phase}"
    assert config.watch_paths == []
    assert config.debounce_phase == 2000
    assert config.make_command is None
