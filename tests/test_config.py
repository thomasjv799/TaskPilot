import pytest
import yaml
from service.config import load_config, Config

def write_config(tmp_path, data):
    f = tmp_path / ".taskpilot.yml"
    f.write_text(yaml.dump(data))
    return str(f)

VALID = {
    "github": {"repo": "owner/repo", "project_number": 1},
    "discord": {
        "project_channel_id": "123",
        "user_map": {"alice": "456", "bob": "789"},
    },
    "llm": {"provider": "groq", "model": "llama-3.1-70b-versatile"},
    "sprint": {"duration_days": 14, "approval_timeout_hours": 24},
}

def test_load_valid_config(tmp_path):
    config = load_config(write_config(tmp_path, VALID))
    assert config.github.repo == "owner/repo"
    assert config.github.project_number == 1
    assert config.discord.project_channel_id == "123"
    assert config.discord.user_map["alice"] == "456"
    assert config.llm.provider == "groq"
    assert config.sprint.duration_days == 14

def test_sprint_defaults_when_omitted(tmp_path):
    data = {**VALID}
    del data["sprint"]
    config = load_config(write_config(tmp_path, data))
    assert config.sprint.duration_days == 14
    assert config.sprint.approval_timeout_hours == 24

def test_missing_github_raises(tmp_path):
    data = {k: v for k, v in VALID.items() if k != "github"}
    with pytest.raises(Exception):
        load_config(write_config(tmp_path, data))

def test_missing_discord_raises(tmp_path):
    data = {k: v for k, v in VALID.items() if k != "discord"}
    with pytest.raises(Exception):
        load_config(write_config(tmp_path, data))

def test_missing_llm_raises(tmp_path):
    data = {k: v for k, v in VALID.items() if k != "llm"}
    with pytest.raises(Exception):
        load_config(write_config(tmp_path, data))
