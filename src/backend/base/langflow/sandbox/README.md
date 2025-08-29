# Langflow Sandbox System

## Overview

The Langflow Sandbox System provides secure execution environments for component code using [nsjail](https://github.com/google/nsjail), a lightweight process isolation tool. This system ensures that untrusted or user-modified components run in isolated environments with restricted access to system resources, while verified components can run with full access to required resources.

### Key Features

- **Trust-based execution**: Components are classified as VERIFIED or UNTRUSTED based on code integrity
- **Resource isolation**: CPU, memory, network, and filesystem access controls
- **Secure secret handling**: Controlled access to API keys and sensitive data
- **Component signature verification**: Cryptographic verification of component integrity
- **Configurable security policies**: Flexible configuration for different deployment scenarios

## How It Works

### Component Trust Levels

1. **VERIFIED Components**: Original, unmodified components that match their cryptographic signatures
   - Run without sandbox restrictions
   - Have direct access to decrypted secrets from the database
   - Can access all system resources

2. **UNTRUSTED Components**: User-modified or custom components
   - Execute in isolated nsjail sandbox
   - Limited resource access (CPU, memory, network)
   - Secrets passed as environment variables (if allowed)
   - Cannot access host filesystem directly

### Execution Flow

1. **Component Loading**: When a component is loaded for execution, the system checks if sandboxing is enabled via `LANGFLOW_SANDBOX_ENABLED` environment variable

2. **Trust Verification**: The `ComponentSecurityManager` verifies the component's code against stored signatures to determine trust level

3. **Execution Routing**:
   - **VERIFIED**: Direct execution with full access
   - **UNTRUSTED**: Routed to sandbox if the component supports sandboxing

4. **Sandbox Execution**: For untrusted components:
   - Code is executed in an isolated nsjail container
   - Resources are limited based on security profile
   - Results are serialized back to the main process

### Configuration

The sandbox system can be configured through:

1. **Environment Variables**:
   - `LANGFLOW_SANDBOX_ENABLED`: Enable/disable sandboxing (default: false)
   - `LANGFLOW_SANDBOX_LOCK_COMPONENTS`: Prevent untrusted components from executing (default: false)

2. **Configuration File** (`config.json`):
   ```json
   {
     "allow_secrets_for_untrusted": false,
     "network_enabled": true,
     "max_execution_time_seconds": 30,
     "max_memory_mb": 128,
     "max_code_size_kb": 50,
     "env_params": ["LANGFLOW_SANDBOX_ENABLED"]
   }
   ```

## Technical Specifications

### Core Components

#### 1. **SandboxManager** (`sandbox_manager.py`)
The main orchestrator for sandbox execution.

**Key Methods**:
- `execute_component()`: Main entry point for sandboxed execution
- `_resolve_component_secrets()`: Handles secret resolution for components
- `_prepare_sandbox_code()`: Prepares component code for sandbox execution
- `_execute_in_sandbox()`: Executes code in nsjail with proper isolation

**Features**:
- Dynamic temporary directory creation per execution
- Secret resolution from database or environment variables
- Component parameter serialization and deserialization
- Error handling and result processing

#### 2. **ComponentSecurityManager** (`signature.py`)
Manages component trust verification through cryptographic signatures.

**Key Classes**:
- `ComponentSignature`: Represents a component's cryptographic signature
- `ComponentSecurityManager`: Verifies component integrity and determines trust level

**Key Methods**:
- `verify_component_signature()`: Checks if component code matches stored signatures
- `supports_sandboxing()`: Checks if a component can run in sandbox
- `is_force_sandbox()`: Determines if a component must always run in sandbox

#### 3. **SecurityPolicy** (`policies.py`)
Defines security profiles and sandbox configurations.

**Key Classes**:
- `SandboxProfile`: Configuration for sandbox execution environment
- `NsjailConfig`: nsjail-specific parameters
- `SecurityPolicy`: Manages security profiles and policies

**Default Restrictions**:
- CPU: 1 core, 30 seconds execution time
- Memory: 128MB limit
- Network: Configurable (enabled/disabled)
- Filesystem: Read-only system mounts, isolated temp directory

#### 4. **SandboxExecutionContext** (`sandbox_context.py`)
Execution context and result handling.

**Key Classes**:
- `ComponentTrustLevel`: Enum for VERIFIED/UNTRUSTED
- `SandboxExecutionContext`: Execution parameters and metadata
- `SandboxExecutionResult`: Execution results and metrics
- `SandboxConfig`: Global sandbox configuration

#### 5. **Component Executor** (`component_executor.py`)
Runs inside the sandbox to execute component code.

**Key Functions**:
- `setup_environment()`: Configures Python paths and environment
- `setup_mock_services()`: Provides mock services for sandboxed execution
- `execute_component()`: Executes the component and returns results

#### Secret Handling

Secrets are handled differently based on trust level:

1. **VERIFIED Components**: Direct database access to decrypt secrets
2. **UNTRUSTED Components**: 
   - If `allow_secrets_for_untrusted` is true: Secrets passed as `LANGFLOW_SECRET_*` environment variables
   - If false: Empty strings are provided for all secret fields

### Component Manifest

The `sandbox_manifest.py` file maintains a list of components tested and verified to work in the sandbox:

```python
SANDBOX_MANIFEST = [
    SandboxComponentManifest(
        name="APIRequest",
        class_name="APIRequestComponent",
        notes="Tested and works as expected."
    ),
    SandboxComponentManifest(
        name="CustomComponent",
        class_name="CustomComponent",
        force_sandbox=True,
        notes="Base custom component template..."
    ),
    # ... more components
]
```

### Component Signature Persistence

The system maintains a historical record of component signatures to ensure that older versions remain trusted even after upgrades:

#### How It Works

1. **Database Storage** (`components` table):
   - All component signatures are persisted in the main Langflow database
   - Each component can have multiple versions with their signatures
   - Signatures are never deleted, only added

2. **Signature Structure**:
   ```sql
   CREATE TABLE components (
       id UUID PRIMARY KEY,
       component_path VARCHAR NOT NULL,  -- e.g., "APIRequestComponent"
       folder VARCHAR NOT NULL,          -- e.g., "data", "agents", "search"
       version VARCHAR NOT NULL,         -- Component version: "1.0", "1.1", etc.
       code TEXT NOT NULL,               -- Full component source code
       signature VARCHAR NOT NULL,       -- HMAC signature: "def456..."
       created_at DATETIME NOT NULL      -- "2024-01-15T10:30:00"
   );
   ```
   
   **Unique Constraint**: `(folder, component_path, version)` - allows same component name in different folders

3. **Version Compatibility**:
   - When verifying a component, the system checks against ALL stored versions
   - If the component matches ANY historical signature, it's considered VERIFIED
   - This allows flows created with older component versions to continue working

4. **Signature Generation**:
   - Code is normalized (comments removed, whitespace standardized) using AST
   - HMAC-SHA256 signature provides both integrity and authenticity
   - Signatures use the Langflow auth secret key for signing

#### Benefits

- **Backward Compatibility**: Flows using older component versions remain functional
- **Upgrade Safety**: Component updates don't break existing flows
- **Audit Trail**: Complete history of component changes
- **Trust Persistence**: Once verified, a component version remains trusted

### Integration Points

#### 1. **Component Loading** (`interface/initialize/loading.py`)
The `build_vertex` function determines execution path:
- Checks if sandboxing is enabled
- Verifies component trust level
- Routes to appropriate execution method

#### 2. **API Integration** (`api/v1/flows.py`)
The `_add_sandbox_flags` function adds sandbox status to flow data:
- Marks components as modified/unmodified
- Indicates sandbox support
- Shows trust level in UI

#### 3. **Service Layer** (`services/sandbox/`)
The `SandboxService` provides:
- Singleton sandbox manager instance
- Service lifecycle management
- Configuration from settings

### Security Considerations

1. **Code Size Limits**: Prevents resource exhaustion from large code submissions
2. **Execution Timeouts**: Prevents infinite loops and resource hogging
3. **Network Isolation**: Optional network access control
4. **Filesystem Isolation**: Prevents access to sensitive host data
5. **Process Isolation**: Prevents interference with other processes

### Performance Impact

- **Overhead**: ~100-200ms for sandbox initialization
- **Memory**: Additional memory for nsjail process
- **CPU**: Minimal overhead for process isolation

### Limitations

1. **Component Compatibility**: Not all components support sandboxing
2. **Library Access**: Some Python libraries may not work in restricted environment
3. **Performance**: Slight overhead for sandbox initialization
4. **Debugging**: Limited debugging capabilities in sandbox

## UI Integration and Visual Indicators

### Component Status Indicators

The frontend displays visual indicators to show the security status of components:

1. **Unmodified/Trusted Components** (These appear as normal):
   - Code matches known signatures
   - Run with full system access

2. **Component will be Sandboxed** (🛡️ Shield):
   - Indicate custom/modified code (Untrusted components)
   - Will be executed in Sandbox

3. **Locked** (🔒 Lock):
   - Code editing not supported for component
   - Applies to components that are not in the sandbox compability list

## Usage Examples

### Enabling Sandboxing

```bash
# Enable sandboxing
export LANGFLOW_SANDBOX_ENABLED=true

# Lock untrusted components (prevent execution)
export LANGFLOW_SANDBOX_LOCK_COMPONENTS=true

# Start Langflow
langflow run
```

### Configuration Example

Create `config.json` in the sandbox directory:

```json
{
  "allow_secrets_for_untrusted": true,
  "network_enabled": false,
  "max_execution_time_seconds": 60,
  "max_memory_mb": 256,
  "max_code_size_kb": 100,
  "env_params": ["LANGFLOW_*", "OPENAI_API_KEY"]
}
```