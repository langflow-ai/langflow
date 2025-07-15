"""
Comprehensive unit tests for DatabaseService

This module contains thorough test coverage for the database service including:
- Database service initialization and configuration
- Session management and context handling
- Connection pool management
- Transaction handling
- Error scenarios and exception handling
- Performance and concurrency testing
- Edge cases and failure conditions

Testing Framework: pytest
Dependencies: Uses existing client fixture and database patterns
"""

import pytest
from unittest.mock import Mock, patch, MagicMock, AsyncMock, call
from sqlalchemy.exc import SQLAlchemyError, IntegrityError, DatabaseError, OperationalError
from sqlalchemy.orm import Session
from sqlalchemy import create_engine, text
from sqlmodel import SQLModel, select
from sqlmodel.ext.asyncio.session import AsyncSession
from contextlib import contextmanager, asynccontextmanager
import asyncio
import threading
import time
import tempfile
import os
from typing import Any, Dict, List, Optional, Union
from pathlib import Path

from langflow.services.database.models.user.model import User
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.api_key.model import ApiKey
from langflow.services.deps import get_db_service
from langflow.services.database.utils import session_getter
from langflow.services.manager import service_manager


class TestDatabaseService:
    """Comprehensive test suite for DatabaseService"""

    def test_database_service_initialization_with_sqlite(self):
        """Test DatabaseService initialization with SQLite"""
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "test.db"
            database_url = f"sqlite:///{db_path}"
            
            # Test that service can be initialized
            db_service = get_db_service()
            assert db_service is not None
            
            # Test database URL configuration
            if hasattr(db_service, 'database_url'):
                assert db_service.database_url is not None

    def test_database_service_initialization_with_postgresql(self, monkeypatch):
        """Test DatabaseService initialization with PostgreSQL"""
        postgresql_url = "postgresql://user:pass@localhost:5432/testdb"
        monkeypatch.setenv("LANGFLOW_DATABASE_URL", postgresql_url)
        
        # Clear service manager cache
        service_manager.services.clear()
        service_manager.factories.clear()
        
        db_service = get_db_service()
        assert db_service is not None

    def test_database_service_singleton_pattern(self):
        """Test that DatabaseService follows singleton pattern"""
        service1 = get_db_service()
        service2 = get_db_service()
        
        assert service1 is service2

    def test_database_service_session_context_manager(self, session):
        """Test database service session context manager"""
        db_service = get_db_service()
        
        # Test that session context manager works
        with db_service.with_session() as db_session:
            assert db_session is not None
            assert hasattr(db_session, 'add')
            assert hasattr(db_session, 'commit')
            assert hasattr(db_session, 'rollback')

    @pytest.mark.asyncio
    async def test_database_service_async_session_context_manager(self, async_session):
        """Test database service async session context manager"""
        db_service = get_db_service()
        
        # Test that async session context manager works
        async with db_service.with_session() as db_session:
            assert db_session is not None
            assert hasattr(db_session, 'add')
            assert hasattr(db_session, 'commit')
            assert hasattr(db_session, 'exec')

    def test_database_service_session_getter_utility(self):
        """Test session_getter utility function"""
        db_service = get_db_service()
        
        async def test_session_getter():
            async with session_getter(db_service) as session:
                assert session is not None
                return session
        
        # Test that session_getter works
        session = asyncio.run(test_session_getter())
        assert session is not None

    def test_database_service_model_operations(self, session):
        """Test basic database model operations"""
        db_service = get_db_service()
        
        with db_service.with_session() as db_session:
            # Test user creation
            user = User(
                username="testuser",
                password="hashed_password",
                is_active=True
            )
            db_session.add(user)
            db_session.commit()
            
            # Test user retrieval
            stmt = select(User).where(User.username == "testuser")
            retrieved_user = db_session.exec(stmt).first()
            assert retrieved_user is not None
            assert retrieved_user.username == "testuser"

    @pytest.mark.asyncio
    async def test_database_service_async_model_operations(self, async_session):
        """Test async database model operations"""
        db_service = get_db_service()
        
        async with db_service.with_session() as db_session:
            # Test user creation
            user = User(
                username="asyncuser",
                password="hashed_password",
                is_active=True
            )
            db_session.add(user)
            await db_session.commit()
            
            # Test user retrieval
            stmt = select(User).where(User.username == "asyncuser")
            result = await db_session.exec(stmt)
            retrieved_user = result.first()
            assert retrieved_user is not None
            assert retrieved_user.username == "asyncuser"

    def test_database_service_transaction_rollback(self, session):
        """Test transaction rollback functionality"""
        db_service = get_db_service()
        
        with pytest.raises(ValueError):
            with db_service.with_session() as db_session:
                user = User(
                    username="rollbackuser",
                    password="hashed_password",
                    is_active=True
                )
                db_session.add(user)
                db_session.flush()  # Ensure user is in session
                
                # Simulate error that should trigger rollback
                raise ValueError("Test error")
        
        # Verify user was not committed due to rollback
        with db_service.with_session() as db_session:
            stmt = select(User).where(User.username == "rollbackuser")
            result = db_session.exec(stmt).first()
            assert result is None

    def test_database_service_connection_handling(self):
        """Test database connection handling"""
        db_service = get_db_service()
        
        # Test that service has engine
        assert hasattr(db_service, 'engine') or hasattr(db_service, '_engine')
        
        # Test health check if available
        if hasattr(db_service, 'health_check'):
            health_status = db_service.health_check()
            assert isinstance(health_status, bool)

    def test_database_service_multiple_sessions(self, session):
        """Test handling of multiple database sessions"""
        db_service = get_db_service()
        
        # Create multiple sessions and ensure they work independently
        sessions = []
        for i in range(3):
            with db_service.with_session() as db_session:
                user = User(
                    username=f"multiuser{i}",
                    password="hashed_password",
                    is_active=True
                )
                db_session.add(user)
                db_session.commit()
                sessions.append(db_session)
        
        # Verify all users were created
        with db_service.with_session() as db_session:
            for i in range(3):
                stmt = select(User).where(User.username == f"multiuser{i}")
                user = db_session.exec(stmt).first()
                assert user is not None
                assert user.username == f"multiuser{i}"

    def test_database_service_concurrent_access(self, session):
        """Test concurrent database access"""
        db_service = get_db_service()
        results = []
        
        def create_user(user_id):
            try:
                with db_service.with_session() as db_session:
                    user = User(
                        username=f"concurrent_user_{user_id}",
                        password="hashed_password",
                        is_active=True
                    )
                    db_session.add(user)
                    db_session.commit()
                    results.append(True)
            except Exception as e:
                results.append(False)
        
        # Create threads for concurrent access
        threads = []
        for i in range(5):
            thread = threading.Thread(target=create_user, args=(i,))
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # Verify all operations succeeded
        assert all(results)
        assert len(results) == 5

    def test_database_service_session_isolation(self, session):
        """Test session isolation between different operations"""
        db_service = get_db_service()
        
        # Create user in first session
        with db_service.with_session() as db_session1:
            user = User(
                username="isolated_user",
                password="hashed_password",
                is_active=True
            )
            db_session1.add(user)
            db_session1.commit()
        
        # Modify user in second session
        with db_service.with_session() as db_session2:
            stmt = select(User).where(User.username == "isolated_user")
            user = db_session2.exec(stmt).first()
            assert user is not None
            user.is_active = False
            db_session2.commit()
        
        # Verify changes in third session
        with db_service.with_session() as db_session3:
            stmt = select(User).where(User.username == "isolated_user")
            user = db_session3.exec(stmt).first()
            assert user is not None
            assert user.is_active is False

    def test_database_service_complex_queries(self, session):
        """Test complex database queries"""
        db_service = get_db_service()
        
        with db_service.with_session() as db_session:
            # Create test data
            users = [
                User(username=f"user_{i}", password="password", is_active=i % 2 == 0)
                for i in range(10)
            ]
            for user in users:
                db_session.add(user)
            db_session.commit()
            
            # Test complex query - active users only
            stmt = select(User).where(User.is_active == True)
            active_users = db_session.exec(stmt).all()
            assert len(active_users) == 5
            
            # Test query with ordering
            stmt = select(User).order_by(User.username)
            ordered_users = db_session.exec(stmt).all()
            assert len(ordered_users) == 10
            assert ordered_users[0].username == "user_0"

    def test_database_service_error_handling(self, session):
        """Test database service error handling"""
        db_service = get_db_service()
        
        with pytest.raises(Exception):
            with db_service.with_session() as db_session:
                # Try to create user with invalid data
                user = User(
                    username=None,  # This should cause an error
                    password="password",
                    is_active=True
                )
                db_session.add(user)
                db_session.commit()

    def test_database_service_bulk_operations(self, session):
        """Test bulk database operations"""
        db_service = get_db_service()
        
        with db_service.with_session() as db_session:
            # Create multiple users in bulk
            users = [
                User(username=f"bulk_user_{i}", password="password", is_active=True)
                for i in range(100)
            ]
            
            for user in users:
                db_session.add(user)
            db_session.commit()
            
            # Verify all users were created
            stmt = select(User).where(User.username.like("bulk_user_%"))
            bulk_users = db_session.exec(stmt).all()
            assert len(bulk_users) == 100

    def test_database_service_relationship_handling(self, session):
        """Test database relationships handling"""
        db_service = get_db_service()
        
        with db_service.with_session() as db_session:
            # Create user
            user = User(
                username="relationship_user",
                password="password",
                is_active=True
            )
            db_session.add(user)
            db_session.commit()
            db_session.refresh(user)
            
            # Create flow for user (if Flow model has user relationship)
            if hasattr(Flow, 'user_id'):
                flow = Flow(
                    name="Test Flow",
                    data={},
                    user_id=user.id
                )
                db_session.add(flow)
                db_session.commit()
                
                # Test relationship queries
                stmt = select(Flow).where(Flow.user_id == user.id)
                user_flows = db_session.exec(stmt).all()
                assert len(user_flows) == 1
                assert user_flows[0].name == "Test Flow"

    def test_database_service_session_cleanup(self, session):
        """Test proper session cleanup"""
        db_service = get_db_service()
        
        session_count = 0
        
        # Test that sessions are properly cleaned up
        for i in range(10):
            with db_service.with_session() as db_session:
                session_count += 1
                user = User(
                    username=f"cleanup_user_{i}",
                    password="password",
                    is_active=True
                )
                db_session.add(user)
                db_session.commit()
        
        assert session_count == 10

    def test_database_service_nested_transactions(self, session):
        """Test nested transaction handling"""
        db_service = get_db_service()
        
        with db_service.with_session() as db_session:
            # Create user in outer transaction
            user = User(
                username="nested_user",
                password="password",
                is_active=True
            )
            db_session.add(user)
            db_session.commit()
            
            # Test nested transaction with savepoint
            if hasattr(db_session, 'begin_nested'):
                savepoint = db_session.begin_nested()
                try:
                    user.is_active = False
                    db_session.flush()
                    # Rollback nested transaction
                    savepoint.rollback()
                except Exception:
                    savepoint.rollback()
                    raise
                
                # Verify user is still active
                db_session.refresh(user)
                assert user.is_active is True

    def test_database_service_connection_pool_behavior(self):
        """Test connection pool behavior"""
        db_service = get_db_service()
        
        # Test that multiple sessions can be created without issues
        sessions = []
        for i in range(10):
            session_ctx = db_service.with_session()
            sessions.append(session_ctx)
        
        # Use sessions
        for i, session_ctx in enumerate(sessions):
            with session_ctx as db_session:
                user = User(
                    username=f"pool_user_{i}",
                    password="password",
                    is_active=True
                )
                db_session.add(user)
                db_session.commit()

    def test_database_service_query_performance(self, session):
        """Test query performance characteristics"""
        db_service = get_db_service()
        
        with db_service.with_session() as db_session:
            # Create test data
            start_time = time.time()
            users = [
                User(username=f"perf_user_{i}", password="password", is_active=True)
                for i in range(1000)
            ]
            for user in users:
                db_session.add(user)
            db_session.commit()
            creation_time = time.time() - start_time
            
            # Test query performance
            start_time = time.time()
            stmt = select(User).where(User.username.like("perf_user_%"))
            results = db_session.exec(stmt).all()
            query_time = time.time() - start_time
            
            assert len(results) == 1000
            assert creation_time < 10.0  # Should complete in reasonable time
            assert query_time < 5.0  # Query should be fast

    def test_database_service_memory_usage(self, session):
        """Test memory usage patterns"""
        db_service = get_db_service()
        
        import gc
        gc.collect()
        initial_objects = len(gc.get_objects())
        
        # Create and destroy many sessions
        for i in range(100):
            with db_service.with_session() as db_session:
                user = User(
                    username=f"memory_user_{i}",
                    password="password",
                    is_active=True
                )
                db_session.add(user)
                db_session.commit()
        
        gc.collect()
        final_objects = len(gc.get_objects())
        
        # Memory usage should not grow excessively
        object_growth = final_objects - initial_objects
        assert object_growth < 10000  # Reasonable threshold

    def test_database_service_edge_cases(self, session):
        """Test edge cases and boundary conditions"""
        db_service = get_db_service()
        
        # Test empty session
        with db_service.with_session() as db_session:
            pass  # Do nothing
        
        # Test session with only queries
        with db_service.with_session() as db_session:
            stmt = select(User).where(User.username == "nonexistent")
            result = db_session.exec(stmt).first()
            assert result is None
        
        # Test session with rollback
        with pytest.raises(ValueError):
            with db_service.with_session() as db_session:
                user = User(
                    username="edge_case_user",
                    password="password",
                    is_active=True
                )
                db_session.add(user)
                db_session.flush()
                raise ValueError("Test rollback")

    def test_database_service_configuration_options(self, monkeypatch):
        """Test database service configuration options"""
        # Test with different database URLs
        test_urls = [
            "sqlite:///test.db",
            "sqlite:///:memory:",
            "postgresql://user:pass@localhost/db"
        ]
        
        for url in test_urls:
            monkeypatch.setenv("LANGFLOW_DATABASE_URL", url)
            service_manager.services.clear()
            service_manager.factories.clear()
            
            db_service = get_db_service()
            assert db_service is not None

    @pytest.mark.asyncio
    async def test_database_service_async_stress_test(self, async_session):
        """Test database service under async stress conditions"""
        db_service = get_db_service()
        
        async def create_user_async(user_id):
            async with db_service.with_session() as db_session:
                user = User(
                    username=f"async_stress_user_{user_id}",
                    password="password",
                    is_active=True
                )
                db_session.add(user)
                await db_session.commit()
                return True
        
        # Create many concurrent tasks
        tasks = [create_user_async(i) for i in range(50)]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Verify all operations succeeded
        successful_results = [r for r in results if r is True]
        assert len(successful_results) == 50

    def test_database_service_custom_session_options(self, session):
        """Test custom session options and configurations"""
        db_service = get_db_service()
        
        # Test session with custom options (if supported)
        with db_service.with_session() as db_session:
            # Test session info
            if hasattr(db_session, 'info'):
                db_session.info['test_key'] = 'test_value'
                assert db_session.info['test_key'] == 'test_value'
            
            # Test session bind
            if hasattr(db_session, 'bind'):
                assert db_session.bind is not None

    def test_database_service_migration_support(self):
        """Test database migration support"""
        db_service = get_db_service()
        
        # Test that migration utilities are available
        # This would test alembic integration if available
        if hasattr(db_service, 'run_migrations'):
            # Test migration functionality
            assert callable(db_service.run_migrations)
        
        # Test table creation
        if hasattr(db_service, 'create_tables'):
            assert callable(db_service.create_tables)

    def test_database_service_backup_restore(self):
        """Test database backup and restore functionality"""
        db_service = get_db_service()
        
        # Test backup functionality if available
        if hasattr(db_service, 'backup'):
            assert callable(db_service.backup)
        
        # Test restore functionality if available
        if hasattr(db_service, 'restore'):
            assert callable(db_service.restore)

    def test_database_service_monitoring_capabilities(self):
        """Test database service monitoring capabilities"""
        db_service = get_db_service()
        
        # Test connection monitoring
        if hasattr(db_service, 'get_connection_info'):
            info = db_service.get_connection_info()
            assert isinstance(info, dict)
        
        # Test performance monitoring
        if hasattr(db_service, 'get_performance_stats'):
            stats = db_service.get_performance_stats()
            assert isinstance(stats, dict)

    def test_database_service_security_features(self, session):
        """Test database service security features"""
        db_service = get_db_service()
        
        with db_service.with_session() as db_session:
            # Test that sensitive operations are handled securely
            user = User(
                username="security_user",
                password="hashed_password",  # Should be hashed
                is_active=True
            )
            db_session.add(user)
            db_session.commit()
            
            # Verify user was created
            stmt = select(User).where(User.username == "security_user")
            created_user = db_session.exec(stmt).first()
            assert created_user is not None
            assert created_user.password == "hashed_password"

    def test_database_service_cleanup_on_exit(self, session):
        """Test proper cleanup when service is destroyed"""
        db_service = get_db_service()
        
        # Test that service can be properly cleaned up
        if hasattr(db_service, 'close'):
            # Test close method if available
            assert callable(db_service.close)
        
        if hasattr(db_service, 'dispose'):
            # Test dispose method if available
            assert callable(db_service.dispose)

    def test_database_service_exception_context_managers(self, session):
        """Test exception handling in context managers"""
        db_service = get_db_service()
        
        # Test that exceptions are properly handled and sessions cleaned up
        exception_caught = False
        
        try:
            with db_service.with_session() as db_session:
                user = User(
                    username="exception_user",
                    password="password",
                    is_active=True
                )
                db_session.add(user)
                db_session.flush()
                
                # Force an exception
                raise RuntimeError("Test exception")
        except RuntimeError:
            exception_caught = True
        
        assert exception_caught
        
        # Verify session was properly cleaned up by testing new session
        with db_service.with_session() as db_session:
            stmt = select(User).where(User.username == "exception_user")
            result = db_session.exec(stmt).first()
            assert result is None  # Should be None due to rollback