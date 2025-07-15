"""
Unit tests for the cache factory module.

This module tests the cache factory implementation, focusing on:
- Factory creation and initialization
- Different cache backend instantiation
- Configuration validation
- Error handling scenarios
- Factory method behavior with various inputs
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from typing import Any, Dict, Optional
from langflow.services.cache.factory import CacheFactory, CacheBackend
from langflow.services.cache.backends.memory import MemoryCache
from langflow.services.cache.backends.redis import RedisCache
from langflow.services.cache.exceptions import CacheConfigurationError, CacheBackendError


class TestCacheFactory:
    """Test cases for the CacheFactory class."""
    
    def test_factory_initialization(self):
        """Test factory can be initialized with default configuration."""
        factory = CacheFactory()
        assert factory is not None
        assert hasattr(factory, 'create_cache')
        assert hasattr(factory, 'get_supported_backends')
    
    def test_factory_initialization_with_config(self):
        """Test factory initialization with custom configuration."""
        config = {
            'default_backend': 'redis',
            'redis_url': 'redis://localhost:6379',
            'memory_max_size': 1000
        }
        factory = CacheFactory(config)
        assert factory.config == config
        assert factory.default_backend == 'redis'
    
    def test_create_memory_cache(self):
        """Test creating a memory cache backend."""
        factory = CacheFactory()
        cache = factory.create_cache('memory')
        assert isinstance(cache, MemoryCache)
        assert cache.max_size == 500  # Default value
    
    def test_create_memory_cache_with_custom_size(self):
        """Test creating memory cache with custom size configuration."""
        config = {'memory_max_size': 1000}
        factory = CacheFactory(config)
        cache = factory.create_cache('memory', max_size=1000)
        assert isinstance(cache, MemoryCache)
        assert cache.max_size == 1000
    
    @patch('langflow.services.cache.backends.redis.Redis')
    def test_create_redis_cache(self, mock_redis):
        """Test creating a Redis cache backend."""
        mock_redis_instance = Mock()
        mock_redis.return_value = mock_redis_instance
        
        factory = CacheFactory()
        cache = factory.create_cache('redis', redis_url='redis://localhost:6379')
        
        assert isinstance(cache, RedisCache)
        mock_redis.assert_called_once_with.from_url('redis://localhost:6379')
    
    @patch('langflow.services.cache.backends.redis.Redis')
    def test_create_redis_cache_with_config(self, mock_redis):
        """Test creating Redis cache using factory configuration."""
        mock_redis_instance = Mock()
        mock_redis.return_value = mock_redis_instance
        
        config = {'redis_url': 'redis://localhost:6379'}
        factory = CacheFactory(config)
        cache = factory.create_cache('redis')
        
        assert isinstance(cache, RedisCache)
        mock_redis.assert_called_once_with.from_url('redis://localhost:6379')
    
    def test_create_cache_invalid_backend(self):
        """Test creating cache with invalid backend raises error."""
        factory = CacheFactory()
        
        with pytest.raises(CacheBackendError) as exc_info:
            factory.create_cache('invalid_backend')
        
        assert 'Unsupported cache backend: invalid_backend' in str(exc_info.value)
    
    def test_create_cache_missing_config(self):
        """Test creating cache without required configuration raises error."""
        factory = CacheFactory()
        
        with pytest.raises(CacheConfigurationError) as exc_info:
            factory.create_cache('redis')  # Missing redis_url
        
        assert 'Missing required configuration for redis backend' in str(exc_info.value)
    
    def test_get_supported_backends(self):
        """Test getting list of supported cache backends."""
        factory = CacheFactory()
        backends = factory.get_supported_backends()
        
        assert isinstance(backends, list)
        assert 'memory' in backends
        assert 'redis' in backends
        assert len(backends) >= 2
    
    def test_create_cache_with_default_backend(self):
        """Test creating cache using default backend when no backend specified."""
        config = {'default_backend': 'memory'}
        factory = CacheFactory(config)
        cache = factory.create_cache()
        
        assert isinstance(cache, MemoryCache)
    
    def test_create_cache_with_kwargs_override(self):
        """Test that kwargs override factory configuration."""
        config = {'memory_max_size': 500}
        factory = CacheFactory(config)
        cache = factory.create_cache('memory', max_size=1000)
        
        assert isinstance(cache, MemoryCache)
        assert cache.max_size == 1000  # kwargs override config
    
    def test_factory_singleton_behavior(self):
        """Test that factory maintains singleton-like behavior for same config."""
        config = {'default_backend': 'memory'}
        factory1 = CacheFactory(config)
        factory2 = CacheFactory(config)
        
        # Should be different instances but behave consistently
        assert factory1 is not factory2
        assert factory1.config == factory2.config
    
    @patch('langflow.services.cache.backends.redis.Redis')
    def test_redis_connection_error_handling(self, mock_redis):
        """Test handling Redis connection errors."""
        mock_redis.side_effect = ConnectionError("Redis connection failed")
        
        factory = CacheFactory()
        
        with pytest.raises(CacheBackendError) as exc_info:
            factory.create_cache('redis', redis_url='redis://localhost:6379')
        
        assert 'Failed to connect to Redis' in str(exc_info.value)
    
    def test_memory_cache_with_zero_size(self):
        """Test memory cache creation with zero size."""
        factory = CacheFactory()
        
        with pytest.raises(CacheConfigurationError) as exc_info:
            factory.create_cache('memory', max_size=0)
        
        assert 'Memory cache size must be positive' in str(exc_info.value)
    
    def test_memory_cache_with_negative_size(self):
        """Test memory cache creation with negative size."""
        factory = CacheFactory()
        
        with pytest.raises(CacheConfigurationError) as exc_info:
            factory.create_cache('memory', max_size=-100)
        
        assert 'Memory cache size must be positive' in str(exc_info.value)
    
    def test_create_cache_with_none_backend(self):
        """Test creating cache with None backend."""
        factory = CacheFactory()
        
        with pytest.raises(CacheBackendError) as exc_info:
            factory.create_cache(None)
        
        assert 'Backend cannot be None' in str(exc_info.value)
    
    def test_create_cache_with_empty_string_backend(self):
        """Test creating cache with empty string backend."""
        factory = CacheFactory()
        
        with pytest.raises(CacheBackendError) as exc_info:
            factory.create_cache('')
        
        assert 'Backend cannot be empty' in str(exc_info.value)
    
    def test_factory_config_validation(self):
        """Test factory configuration validation."""
        invalid_config = {
            'default_backend': 'invalid_backend',
            'redis_url': None,
            'memory_max_size': 'invalid_size'
        }
        
        with pytest.raises(CacheConfigurationError) as exc_info:
            CacheFactory(invalid_config)
        
        assert 'Invalid factory configuration' in str(exc_info.value)
    
    @patch('langflow.services.cache.backends.redis.Redis')
    def test_redis_cache_with_custom_settings(self, mock_redis):
        """Test Redis cache creation with custom settings."""
        mock_redis_instance = Mock()
        mock_redis.return_value = mock_redis_instance
        
        factory = CacheFactory()
        cache = factory.create_cache(
            'redis',
            redis_url='redis://localhost:6379',
            db=1,
            decode_responses=True,
            socket_timeout=30
        )
        
        assert isinstance(cache, RedisCache)
        mock_redis.assert_called_once_with.from_url(
            'redis://localhost:6379',
            db=1,
            decode_responses=True,
            socket_timeout=30
        )
    
    def test_create_multiple_cache_instances(self):
        """Test creating multiple cache instances with same configuration."""
        factory = CacheFactory()
        cache1 = factory.create_cache('memory', max_size=100)
        cache2 = factory.create_cache('memory', max_size=100)
        
        assert isinstance(cache1, MemoryCache)
        assert isinstance(cache2, MemoryCache)
        assert cache1 is not cache2  # Different instances
        assert cache1.max_size == cache2.max_size
    
    def test_factory_with_environment_variables(self):
        """Test factory respects environment variables for configuration."""
        with patch.dict('os.environ', {
            'LANGFLOW_CACHE_BACKEND': 'redis',
            'LANGFLOW_REDIS_URL': 'redis://localhost:6379'
        }):
            factory = CacheFactory()
            assert factory.default_backend == 'redis'
    
    def test_create_cache_with_ttl_config(self):
        """Test creating cache with TTL configuration."""
        factory = CacheFactory()
        cache = factory.create_cache('memory', default_ttl=300)
        
        assert isinstance(cache, MemoryCache)
        assert cache.default_ttl == 300
    
    def test_factory_repr(self):
        """Test factory string representation."""
        config = {'default_backend': 'memory'}
        factory = CacheFactory(config)
        repr_str = repr(factory)
        
        assert 'CacheFactory' in repr_str
        assert 'memory' in repr_str
    
    def test_factory_context_manager(self):
        """Test factory can be used as context manager."""
        factory = CacheFactory()
        
        with factory as f:
            cache = f.create_cache('memory')
            assert isinstance(cache, MemoryCache)
    
    def test_create_cache_with_custom_serializer(self):
        """Test creating cache with custom serializer."""
        custom_serializer = Mock()
        factory = CacheFactory()
        cache = factory.create_cache('memory', serializer=custom_serializer)
        
        assert isinstance(cache, MemoryCache)
        assert cache.serializer == custom_serializer
    
    def test_factory_thread_safety(self):
        """Test factory is thread-safe for concurrent cache creation."""
        import threading
        import time
        
        factory = CacheFactory()
        caches = []
        
        def create_cache():
            cache = factory.create_cache('memory')
            caches.append(cache)
            time.sleep(0.01)  # Simulate some work
        
        threads = [threading.Thread(target=create_cache) for _ in range(10)]
        
        for thread in threads:
            thread.start()
        
        for thread in threads:
            thread.join()
        
        assert len(caches) == 10
        assert all(isinstance(cache, MemoryCache) for cache in caches)
    
    def test_factory_reset_configuration(self):
        """Test resetting factory configuration."""
        factory = CacheFactory({'default_backend': 'redis'})
        assert factory.default_backend == 'redis'
        
        factory.reset_configuration({'default_backend': 'memory'})
        assert factory.default_backend == 'memory'
    
    def test_factory_get_backend_info(self):
        """Test getting backend information."""
        factory = CacheFactory()
        info = factory.get_backend_info('memory')
        
        assert isinstance(info, dict)
        assert 'name' in info
        assert 'description' in info
        assert 'supported_features' in info
    
    def test_factory_validate_backend_config(self):
        """Test validating backend-specific configuration."""
        factory = CacheFactory()
        
        # Valid config
        valid_config = {'max_size': 1000}
        assert factory.validate_backend_config('memory', valid_config) is True
        
        # Invalid config
        invalid_config = {'max_size': 'invalid'}
        assert factory.validate_backend_config('memory', invalid_config) is False
    
    def test_factory_cache_metrics(self):
        """Test factory provides cache metrics."""
        factory = CacheFactory()
        cache = factory.create_cache('memory')
        
        # Simulate some cache operations
        cache.set('key1', 'value1')
        cache.get('key1')
        cache.set('key2', 'value2')
        
        metrics = factory.get_cache_metrics(cache)
        assert isinstance(metrics, dict)
        assert 'hits' in metrics
        assert 'misses' in metrics
        assert 'total_operations' in metrics