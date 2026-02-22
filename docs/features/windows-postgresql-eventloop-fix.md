# Feature: Windows PostgreSQL Event Loop Fix

> Generated on: 2024-02-13  
> Status: Approved  
> Owner: Platform Team / Database Infrastructure

---

## Table of Contents
1. [Overview](#1-overview)
2. [Ubiquitous Language Glossary](#2-ubiquitous-language-glossary)
3. [Domain Model](#3-domain-model)
4. [Behavior Specifications](#4-behavior-specifications)
5. [Architecture Decision Records](#5-architecture-decision-records)
6. [Technical Specification](#6-technical-specification)
7. [Observability](#7-observability)
8. [Deployment & Rollback](#8-deployment--rollback)
9. [Architecture Diagrams](#9-architecture-diagrams)

---

## 1. Overview

### Summary
This feature provides automatic event loop configuration for Windows systems running Langflow with PostgreSQL databases, resolving incompatibility between psycopg (PostgreSQL async driver) and Windows' default ProactorEventLoop.

### Business Context
Windows users experience application startup failures when using PostgreSQL as the database backend due to an incompatibility between the psycopg driver and Windows' default event loop implementation. This prevents Windows users from leveraging PostgreSQL's advanced features and scalability, limiting them to SQLite which may not meet enterprise requirements.

### Bounded Context
Platform Infrastructure - Database Connectivity Layer

### Related Contexts
- **Database Service** (Conformist): Applies event loop configuration during initialization
- **Application Initialization** (Customer-Supplier): Provides early event loop setup
- **Testing Infrastructure** (Partnership): Validates cross-platform compatibility

---

## 2. Ubiquitous Language Glossary

| Term | Definition | Code Reference |
|------|------------|----------------|
| Event Loop | The core async execution mechanism in Python that manages and executes asynchronous tasks | `asyncio.get_event_loop_policy()` |
| ProactorEventLoop | Windows' default event loop implementation using I/O Completion Ports | `asyncio.WindowsProactorEventLoopPolicy` |
| SelectorEventLoop | Alternative Windows event loop using select() system call, compatible with psycopg | `asyncio.WindowsSelectorEventLoopPolicy` |
| psycopg | PostgreSQL adapter for Python with async support | `postgresql+psycopg://` |
| Event Loop Policy | Strategy pattern implementation controlling which event loop type is created | `asyncio.set_event_loop_policy()` |
| Database URL | Connection string specifying database type, credentials, and location | `LANGFLOW_DATABASE_URL` |
| Platform Detection | Runtime identification of the operating system | `platform.system()` |

---

## 3. Domain Model

### 3.1 Aggregates

#### Platform Configuration Aggregate
- **Root Entity**: `WindowsPostgresHelper`
- **Entities**: None (stateless helper)
- **Value Objects**: 
  - `LANGFLOW_DATABASE_URL` (constant)
  - `POSTGRESQL_PREFIXES` (tuple constant)
- **Invariants**: 
  - Event loop policy must be set before any async database operations
  - Configuration only applies when Windows AND PostgreSQL are detected
  - Configuration is idempotent (safe to call multiple times)

### 3.2 Domain Events

| Event | Trigger | Payload | Consumers |
|-------|---------|---------|-----------|
| EventLoopConfigured | Windows + PostgreSQL detected | `{event_loop: "WindowsSelectorEventLoop", reason: "psycopg_compatibility", source: str}` | Logger (debug level) |
| ConfigurationSkipped | Non-Windows or non-PostgreSQL | None | None (silent) |

---

## 4. Behavior Specifications

### Feature: Automatic Event Loop Configuration for Windows PostgreSQL

**As a** Windows user  
**I want** Langflow to automatically configure the correct event loop  
**So that** I can use PostgreSQL without encountering startup errors

### Background
- Given the application is starting
- And the platform detection is available

### Scenario: Windows with PostgreSQL - Apply Fix
- **Given** the operating system is "Windows"
- **And** LANGFLOW_DATABASE_URL starts with "postgresql" or "postgres"
- **And** the current event loop policy is WindowsProactorEventLoopPolicy
- **When** configure_windows_postgres_event_loop() is called
- **Then** WindowsSelectorEventLoopPolicy is set as the event loop policy
- **And** the function returns True
- **And** a debug log is created with context information

### Scenario: Windows with PostgreSQL - Already Configured
- **Given** the operating system is "Windows"
- **And** LANGFLOW_DATABASE_URL starts with "postgresql"
- **And** the current event loop policy is already WindowsSelectorEventLoopPolicy
- **When** configure_windows_postgres_event_loop() is called
- **Then** no changes are made to the event loop policy
- **And** the function returns False

### Scenario: Windows with SQLite - No Fix Needed
- **Given** the operating system is "Windows"
- **And** LANGFLOW_DATABASE_URL is "sqlite:///test.db"
- **When** configure_windows_postgres_event_loop() is called
- **Then** no changes are made to the event loop policy
- **And** the function returns False

### Scenario: Linux with PostgreSQL - No Fix Needed
- **Given** the operating system is "Linux"
- **And** LANGFLOW_DATABASE_URL starts with "postgresql"
- **When** configure_windows_postgres_event_loop() is called
- **Then** no changes are made to the event loop policy
- **And** the function returns False

### Scenario: Docker Container - No Fix Applied
- **Given** the operating system is "Linux" (typical in Docker)
- **And** DOCKER_CONTAINER environment variable is set
- **And** LANGFLOW_DATABASE_URL starts with "postgresql"
- **When** configure_windows_postgres_event_loop() is called
- **Then** no changes are made to the event loop policy
- **And** the function returns False

### Scenario: Missing Database URL
- **Given** the operating system is "Windows"
- **And** LANGFLOW_DATABASE_URL is not set
- **When** configure_windows_postgres_event_loop() is called
- **Then** no changes are made to the event loop policy
- **And** the function returns False

---

## 5. Architecture Decision Records

### ADR-001: Centralized Event Loop Configuration Helper

**Status**: Accepted

#### Context
The psycopg PostgreSQL driver is incompatible with Windows' default ProactorEventLoop, causing `psycopg.InterfaceError` during database connection initialization. The fix requires setting WindowsSelectorEventLoopPolicy before any async operations, but this was initially duplicated across multiple entry points.

#### Decision
Create a centralized helper function `configure_windows_postgres_event_loop()` that encapsulates all event loop configuration logic, following DRY (Don't Repeat Yourself) and Single Responsibility principles.

#### Consequences

**Benefits:**
- Single source of truth for event loop configuration
- Easier maintenance and testing
- Consistent behavior across all entry points
- Clear separation of concerns

**Trade-offs:**
- Additional import required in initialization files
- Slightly increased module coupling

**Impact on Product:**
- Windows users can now use PostgreSQL without configuration changes
- No impact on Linux/macOS users
- No performance degradation

---

### ADR-002: Early Configuration at Multiple Entry Points

**Status**: Accepted

#### Context
The event loop must be configured before any async operations or database imports. Langflow has multiple entry points: package import, launcher, main module, and service initialization.

#### Decision
Apply configuration at all critical entry points to ensure coverage regardless of how Langflow is started:
- `__init__.py` - Package initialization
- `langflow_launcher.py` - CLI launcher
- `__main__.py` - Direct module execution
- `DatabaseService.__init__` - Service initialization
- `initialize_services()` - Service orchestration

#### Consequences

**Benefits:**
- Guaranteed configuration regardless of entry point
- Defensive programming approach
- Idempotent implementation prevents issues from multiple calls

**Trade-offs:**
- Configuration may be called multiple times (mitigated by idempotency)
- Import overhead at package level

**Impact on Product:**
- Robust solution that works with all deployment methods
- No user-visible performance impact

---

### ADR-003: Platform-Specific Event Loop Selection for Uvicorn

**Status**: Accepted

#### Context
Uvicorn web server has its own event loop configuration that can override our settings when specified with `loop="asyncio"` parameter.

#### Decision
Conditionally set Uvicorn's loop parameter to `None` (use existing loop) when Windows + PostgreSQL is detected, allowing our pre-configured WindowsSelectorEventLoopPolicy to remain active.

#### Consequences

**Benefits:**
- Preserves our event loop configuration through web server initialization
- Maintains compatibility with other platforms

**Trade-offs:**
- Uvicorn configuration becomes platform-aware
- Slight deviation from default Uvicorn settings on Windows + PostgreSQL

**Impact on Product:**
- Web server starts successfully with PostgreSQL on Windows
- No impact on other configurations

---

## 6. Technical Specification

### 6.1 Dependencies

| Type | Name | Purpose |
|------|------|---------|
| Python Module | `asyncio` | Event loop management |
| Python Module | `platform` | OS detection |
| Python Module | `os` | Environment variable access |
| Library | `psycopg` | PostgreSQL async driver (external) |
| Library | `sqlalchemy` | Database abstraction layer |
| Service | `DatabaseService` | Database connection management |
| Logger | `lfx.log.logger` | Structured logging |

### 6.2 API Contracts

#### configure_windows_postgres_event_loop(source: str | None = None) -> bool

**Purpose**: Configures Windows event loop for PostgreSQL compatibility

**Parameters**:
```python
source: str | None  # Optional identifier for logging context (e.g., "main", "launcher")
```

**Response (Success)**:
```python
True  # Event loop was configured
```

**Response (No Action)**:
```python
False  # Configuration not needed or already configured
```

### 6.3 Error Handling

| Error Code | Condition | User Message | Recovery Action |
|------------|-----------|--------------|-----------------|
| `psycopg.InterfaceError` | ProactorEventLoop with psycopg | "Psycopg cannot use the 'ProactorEventLoop'" | Automatic - helper prevents this error |
| N/A | Platform detection fails | Silent - returns False | No configuration applied, default behavior |
| N/A | Environment variable missing | Silent - returns False | No configuration applied, uses default |

---

## 7. Observability

### 7.1 Key Metrics

| Metric | Type | Description | Alert Threshold |
|--------|------|-------------|-----------------|
| `event_loop_configuration_applied` | Counter | Number of times configuration was applied | N/A - Informational |
| `event_loop_configuration_skipped` | Counter | Number of times configuration was skipped | N/A - Informational |
| `database_connection_errors` | Counter | PostgreSQL connection failures | > 5 per minute |

### 7.2 Important Logs

| Log Level | Event | Fields | When |
|-----------|-------|--------|------|
| DEBUG | Event loop configured | `event_loop`, `reason`, `source` | Configuration applied |
| INFO | PostgreSQL detected on Windows | `database_url` (sanitized) | Service initialization |
| ERROR | Database connection failed | `error_type`, `platform` | Connection failure |

### 7.3 Dashboards
- Platform distribution of database backends
- Windows PostgreSQL adoption rate
- Event loop configuration frequency by source

---

## 8. Deployment & Rollback

### 8.1 Feature Flags

| Flag | Purpose | Default | Rollout Strategy |
|------|---------|---------|------------------|
| N/A | Feature is always active when conditions are met | Enabled | Automatic based on platform + database detection |

### 8.2 Database Migrations
- None required - this is a client-side connection configuration

### 8.3 Rollback Plan
1. Revert to previous version of Langflow
2. Windows + PostgreSQL users must manually set event loop via environment configuration
3. Or use SQLite as temporary workaround

### 8.4 Smoke Tests
- [ ] Windows + PostgreSQL: Application starts successfully
- [ ] Windows + PostgreSQL: Database queries execute without errors
- [ ] Windows + SQLite: No event loop changes applied
- [ ] Linux + PostgreSQL: No event loop changes applied
- [ ] macOS + PostgreSQL: No event loop changes applied
- [ ] Docker + PostgreSQL: No event loop changes applied

---

## 9. Architecture Diagrams

### 9.1 Context Diagram (Level 1)

```mermaid
C4Context
  title System Context diagram for Windows PostgreSQL Event Loop Fix
  
  Person(dev, "Developer", "Windows user running Langflow")
  System(langflow, "Langflow", "AI application development platform")
  System_Ext(postgres, "PostgreSQL", "Database server")
  System_Ext(sqlite, "SQLite", "File-based database")
  
  Rel(dev, langflow, "Develops AI apps")
  Rel(langflow, postgres, "Stores data (with event loop fix)")
  Rel(langflow, sqlite, "Alternative storage (no fix needed)")
```

### 9.2 Container Diagram (Level 2)

```mermaid
C4Container
  title Container diagram for Event Loop Configuration
  
  Container(helper, "WindowsPostgresHelper", "Python Module", "Event loop configuration")
  Container(launcher, "Launcher", "Python", "Application entry point")
  Container(dbservice, "DatabaseService", "Python", "Database connection management")
  ContainerDb(postgres, "PostgreSQL", "psycopg", "Async database connection")
  
  Rel(launcher, helper, "Calls configure_windows_postgres_event_loop()")
  Rel(dbservice, helper, "Calls configure_windows_postgres_event_loop()")
  Rel(helper, postgres, "Configures compatible event loop")
  Rel(dbservice, postgres, "Establishes connection")
```

### 9.3 Component Diagram (Level 3)

```mermaid
graph TB
    subgraph "Initialization Flow"
        A[Application Start] --> B{Platform Check}
        B -->|Windows| C{Database Check}
        B -->|Linux/Mac| D[Skip Configuration]
        C -->|PostgreSQL| E{Event Loop Check}
        C -->|Other DB| D
        E -->|ProactorEventLoop| F[Set SelectorEventLoop]
        E -->|Already Selector| G[Skip - Already Set]
        F --> H[Log Configuration]
        G --> I[Return False]
        H --> J[Return True]
        D --> I
    end
    
    subgraph "Entry Points"
        K[__init__.py] --> A
        L[launcher.py] --> A
        M[__main__.py] --> A
        N[DatabaseService] --> A
        O[initialize_services] --> A
    end
```

---

## Testing Coverage

### Unit Tests (test_windows_postgres_helper.py)
- ✅ Platform detection (Windows, Linux, macOS, FreeBSD)
- ✅ Database URL detection (PostgreSQL, postgres://, SQLite, MySQL)
- ✅ Event loop policy verification
- ✅ Idempotency testing
- ✅ Logging context validation
- ✅ Docker environment compatibility

### Integration Tests (test_database_windows_postgres_integration.py)
- ✅ DatabaseService initialization with various configurations
- ✅ Cross-platform database URL sanitization
- ✅ Async operation compatibility
- ✅ Service-level event loop configuration

---

## Migration Guide for Existing Users

### For Windows + PostgreSQL Users
No action required. The fix is automatically applied when:
1. Operating system is Windows
2. `LANGFLOW_DATABASE_URL` starts with `postgresql://` or `postgres://`

### For Other Configurations
No changes or impact. The fix only activates for Windows + PostgreSQL combinations.

### Environment Variables
Ensure `LANGFLOW_DATABASE_URL` is properly set in your `.env` file:
```env
LANGFLOW_DATABASE_URL=postgresql://user:password@localhost:5432/langflow
```

---

## Troubleshooting

### Issue: Still Getting ProactorEventLoop Errors

**Symptoms**: `psycopg.InterfaceError: Psycopg cannot use the 'ProactorEventLoop'`

**Solutions**:
1. Ensure you're using the latest version with this fix
2. Check that `LANGFLOW_DATABASE_URL` is properly set before application start
3. Verify no other code is resetting the event loop policy

### Issue: Performance Degradation on Windows

**Symptoms**: Slower async operations on Windows after the fix

**Context**: SelectorEventLoop may have different performance characteristics than ProactorEventLoop

**Solutions**:
1. This is a necessary trade-off for PostgreSQL compatibility
2. Consider using connection pooling to minimize impact
3. For maximum performance with PostgreSQL, consider using WSL2 or Linux

---

## References

- [Python asyncio Event Loops](https://docs.python.org/3/library/asyncio-eventloop.html)
- [Psycopg 3 Documentation](https://www.psycopg.org/psycopg3/docs/)
- [SQLAlchemy Async Support](https://docs.sqlalchemy.org/en/14/orm/extensions/asyncio.html)
- [Windows Event Loop Implementations](https://docs.python.org/3/library/asyncio-platforms.html#windows)