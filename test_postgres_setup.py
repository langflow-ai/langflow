#!/usr/bin/env python3
"""
Test PostgreSQL connection and setup for migration testing
"""
import asyncio
import os
import sys
from pathlib import Path

import psycopg
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError

# Test different PostgreSQL connection URLs
TEST_URLS = [
    "postgresql://postgres:postgres@localhost:5432/postgres",
    "postgresql://postgres@localhost:5432/postgres",
    "postgresql://localhost:5432/postgres",
    "postgresql://postgres:password@localhost:5432/postgres"
]

def test_postgres_connection():
    """Test PostgreSQL connections with different authentication methods"""
    print("🔄 Testing PostgreSQL connection options...\n")

    for i, url in enumerate(TEST_URLS, 1):
        print(f"Test {i}: {url}")
        try:
            # Test with psycopg directly first
            conn_params = psycopg.conninfo.conninfo_to_dict(url.replace("postgresql://", ""))
            conn = psycopg.connect(**conn_params)
            conn.close()
            print(f"✅ psycopg connection successful")

            # Test with SQLAlchemy
            engine = create_engine(url.replace("postgresql://", "postgresql+psycopg://"))
            with engine.connect() as conn:
                result = conn.execute(text("SELECT version()"))
                version = result.fetchone()[0]
                print(f"✅ SQLAlchemy connection successful")
                print(f"   PostgreSQL version: {version[:50]}...")

            print(f"✅ Connection URL works: {url}\n")
            return url

        except Exception as e:
            print(f"❌ Connection failed: {e}\n")
            continue

    return None


def create_test_database(working_url):
    """Create a test database for migration testing"""
    print("🔄 Creating test database for migration testing...")

    try:
        # Connect to postgres database to create test database
        base_url = working_url.rsplit('/', 1)[0] + '/postgres'
        engine = create_engine(base_url.replace("postgresql://", "postgresql+psycopg://"))

        with engine.connect() as conn:
            # Commit the current transaction and start a new one
            conn.commit()
            # Create test database (need to be outside transaction)
            try:
                conn.execute(text("CREATE DATABASE langflow_test"))
                print("✅ Test database 'langflow_test' created")
            except Exception as e:
                if "already exists" in str(e):
                    print("ℹ️  Test database 'langflow_test' already exists")
                else:
                    raise

        # Return the test database URL
        test_url = working_url.rsplit('/', 1)[0] + '/langflow_test'
        print(f"✅ Test database URL: {test_url}")
        return test_url

    except Exception as e:
        print(f"❌ Failed to create test database: {e}")
        return None


def test_migration_with_postgres(test_db_url):
    """Test the actual migration process with PostgreSQL"""
    print("🔄 Testing migration process with PostgreSQL...")

    # Set environment variable for the test
    os.environ['LANGFLOW_DATABASE_URL'] = test_db_url

    # Add src path for imports
    sys.path.insert(0, str(Path(__file__).parent / "src" / "backend" / "base"))

    try:
        from langflow.services.database.service import DatabaseService
        from langflow.services.settings.service import SettingsService

        # Create settings service with the test database URL
        settings_service = SettingsService()
        settings_service.settings.database_url = test_db_url

        # Create database service
        database_service = DatabaseService(settings_service)

        print(f"✅ DatabaseService created with URL: {database_service.database_url}")

        # Test the migration logic
        print("🔄 Testing migration run...")

        async def run_test():
            try:
                # Test basic database operations first
                async with database_service.with_session() as session:
                    # Try to query alembic_version table
                    try:
                        result = await session.exec(text("SELECT * FROM alembic_version"))
                        print("ℹ️  alembic_version table exists")
                        should_init = False
                    except Exception:
                        print("ℹ️  alembic_version table does not exist")
                        should_init = True

                # Run migrations
                await database_service.run_migrations(fix=False)
                print("✅ Migration completed successfully")

                # Verify tables were created
                async with database_service.with_session() as session:
                    result = await session.exec(text("""
                        SELECT table_name
                        FROM information_schema.tables
                        WHERE table_schema = 'public'
                    """))
                    tables = [row[0] for row in result.fetchall()]
                    print(f"✅ Tables created: {tables}")

                return True

            except Exception as e:
                print(f"❌ Migration test failed: {e}")
                import traceback
                traceback.print_exc()
                return False

        # Run the async test
        return asyncio.run(run_test())

    except Exception as e:
        print(f"❌ Setup failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Main test function"""
    print("🧪 PostgreSQL Migration Testing\n")
    print("=" * 50)

    # Step 1: Test PostgreSQL connection
    working_url = test_postgres_connection()
    if not working_url:
        print("❌ Could not establish PostgreSQL connection")
        print("\n💡 Possible solutions:")
        print("1. Start PostgreSQL server: brew services start postgresql")
        print("2. Create postgres user: createuser -s postgres")
        print("3. Set password: psql -U postgres -c \"ALTER USER postgres PASSWORD 'postgres';\"")
        print("4. Check pg_hba.conf authentication settings")
        return False

    print("=" * 50)

    # Step 2: Create test database
    test_db_url = create_test_database(working_url)
    if not test_db_url:
        print("❌ Could not create test database")
        return False

    print("=" * 50)

    # Step 3: Test migration process
    success = test_migration_with_postgres(test_db_url)

    print("=" * 50)

    if success:
        print("🎉 All PostgreSQL migration tests passed!")
        print(f"\n✅ Working database URL: {test_db_url}")
        print("✅ Auto-migration logic works correctly")
        print("✅ Tables are created automatically")
    else:
        print("❌ PostgreSQL migration tests failed")

    return success


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)