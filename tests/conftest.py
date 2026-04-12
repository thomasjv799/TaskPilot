# tests/conftest.py
import pytest
from unittest.mock import AsyncMock, MagicMock


@pytest.fixture
def mock_bot():
    bot = AsyncMock()
    bot.user = MagicMock()
    bot.user.id = 1
    return bot


@pytest.fixture
def mock_config():
    config = MagicMock()
    config.discord.project_channel_id = "123456"
    config.discord.user_map = {"alice": "111", "bob": "222"}
    config.github.repo = "owner/repo"
    return config
