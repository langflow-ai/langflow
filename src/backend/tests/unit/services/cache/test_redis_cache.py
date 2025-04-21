import secrets
import unittest
from unittest.mock import MagicMock, patch

from langflow.services.cache.service import RedisCache


class RedisCacheTest(unittest.TestCase):
    @patch("redis.asyncio.StrictRedis.from_url")
    def test_init_url_initialization(self, mock_from_url):
        mock_client = MagicMock()
        mock_from_url.return_value = mock_client
        cache = RedisCache(url="redis://localhost:6379/0")
        assert cache.is_connected()

    @patch("redis.asyncio.StrictRedis")
    def test_redis_cache_with_password(self, mock_redis):
        mock_client = MagicMock()
        mock_redis.return_value = mock_client
        # random passwordimport secrets
        password = secrets.token_urlsafe(10)
        cache = RedisCache(host="localhost", port=6379, db=0, password=password)
        assert cache.is_connected()
