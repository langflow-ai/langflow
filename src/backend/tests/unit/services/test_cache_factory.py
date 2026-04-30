from pathlib import Path
from types import SimpleNamespace

from langflow.services.cache.disk import AsyncDiskCache
from langflow.services.cache.factory import CacheServiceFactory
from lfx.services.settings.base import Settings


def test_disk_cache_uses_cache_dir_setting(monkeypatch, tmp_path):
    config_dir = tmp_path / "config"
    cache_dir = tmp_path / "cache"
    monkeypatch.setenv("LANGFLOW_CONFIG_DIR", str(config_dir))
    monkeypatch.setenv("LANGFLOW_CACHE_TYPE", "disk")
    monkeypatch.setenv("LANGFLOW_CACHE_DIR", str(cache_dir))

    settings = Settings()
    cache = CacheServiceFactory().create(SimpleNamespace(settings=settings))

    try:
        assert isinstance(cache, AsyncDiskCache)
        assert Path(settings.cache_dir) == cache_dir.resolve()
        assert Path(cache.cache.directory) == cache_dir.resolve()
    finally:
        cache.cache.close()


def test_disk_cache_falls_back_to_config_dir(monkeypatch, tmp_path):
    config_dir = tmp_path / "config"
    monkeypatch.setenv("LANGFLOW_CONFIG_DIR", str(config_dir))
    monkeypatch.setenv("LANGFLOW_CACHE_TYPE", "disk")
    monkeypatch.delenv("LANGFLOW_CACHE_DIR", raising=False)

    settings = Settings()
    cache = CacheServiceFactory().create(SimpleNamespace(settings=settings))

    try:
        assert isinstance(cache, AsyncDiskCache)
        assert settings.cache_dir is None
        assert Path(cache.cache.directory) == config_dir.resolve()
    finally:
        cache.cache.close()
