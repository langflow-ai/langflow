# Builder Agent Installation and Configuration Guide

## Overview

The Builder Agent is a system-level flow that powers the AI Studio's agent building capabilities. It is automatically initialized when the application starts and is stored in a dedicated system folder.

## Architecture

### File Structure

```
src/backend/base/langflow/
├── initial_setup/
│   ├── builder_agent/
│   │   └── BuilderAgent.json          # Builder agent flow definition (single source of truth)
│   ├── constants.py                    # Folder name constants
│   └── setup.py                        # Initialization logic
├── custom/genesis/
│   ├── core/
│   │   └── config.py                   # Environment configuration
│   └── services/agent_builder/
│       └── multi_agent_orchestrator.py # Orchestrator that calls the flow
└── api/v1/
    ├── projects.py                     # Folder access control
    ├── flows.py                        # Flow access control
    └── agent_builder.py                # Agent builder API endpoint
```

## Configuration

### Required Environment Variables

Only one environment variable is required in your `.env` file:

```bash
# Langflow API URL - Base URL for the Langflow API
LANGFLOW_API_URL=http://localhost:7860
```

### Flow ID Configuration

**Important**: The Builder Agent flow ID is **automatically read from BuilderAgent.json** - there is no need to configure it in `.env`.

The flow ID is the single source of truth and is located in:
```
src/backend/base/langflow/initial_setup/builder_agent/BuilderAgent.json
```

Current flow ID: `01752477-a7b3-4622-8420-36d4a6b81476`

## Installation Process

### Automatic Initialization

The Builder Agent flow is automatically initialized when the application starts. The initialization process:

1. **On Application Startup** (`main.py` lifespan):
   - Creates "Builder Agent" system folder (if doesn't exist)
   - Loads BuilderAgent.json from the file system
   - Checks if flow with the ID from JSON already exists in database
   - Creates or updates the flow in the database
   - Ensures the flow is in the Builder Agent folder

2. **System Folder Creation**:
   - Folder name: `"Builder Agent"`
   - `user_id`: `None` (system-owned, not user-owned)
   - Description: `"System folder for builder agent flow"`

3. **Flow Creation/Update**:
   - Flow ID: Read from `BuilderAgent.json`
   - `user_id`: `None` (system-owned)
   - `folder_id`: Builder Agent folder ID
   - All flow data from BuilderAgent.json is preserved

### Migration Support

If a user-owned flow with the same ID exists, the system will:
1. Delete the user-owned flow
2. Recreate it as a system flow with `user_id=None`

This ensures proper migration from development/test flows to production system flows.

## Access Control

### Current Implementation

**Visibility**: The Builder Agent folder and its flows are **visible to all users**.

**Access Levels**:
- ✅ All users can view the Builder Agent folder
- ✅ All users can view flows in the folder
- ✅ All users can access flow details
- ✅ System flows (`user_id=None`) are accessible to everyone

### Future Enhancement (TODO)

Role-based access control should be implemented to restrict the Builder Agent folder to admin users only.

**Affected Files** (marked with TODO comments):
- `src/backend/base/langflow/api/v1/projects.py`
- `src/backend/base/langflow/api/v1/flows.py`
- `src/backend/base/langflow/initial_setup/constants.py`

## Updating the Builder Agent Flow

### Method 1: Update JSON File (Recommended)

1. Export your updated flow from the UI
2. Replace the content of `BuilderAgent.json`:
   ```bash
   cp /path/to/exported/flow.json src/backend/base/langflow/initial_setup/builder_agent/BuilderAgent.json
   ```

3. **Important**: Ensure the flow ID in the JSON matches the expected ID:
   ```bash
   # Verify the ID
   python -c "import json; data=json.load(open('src/backend/base/langflow/initial_setup/builder_agent/BuilderAgent.json')); print('Flow ID:', data['id'])"
   ```

4. Restart the application - the flow will be automatically updated in the database

### Method 2: Update via Database

The flow will be automatically updated on next startup if you:
1. Modify the flow in the UI
2. The changes are saved to the database
3. Export the flow and replace BuilderAgent.json
4. Restart the application

## Troubleshooting

### Flow ID Mismatch

**Symptom**: 404 errors when calling the builder agent flow

**Solution**: 
1. Check the flow ID in BuilderAgent.json:
   ```bash
   python -c "import json; print(json.load(open('src/backend/base/langflow/initial_setup/builder_agent/BuilderAgent.json'))['id'])"
   ```

2. Verify the orchestrator is reading the correct ID:
   - The `MultiAgentOrchestrator` reads the ID directly from BuilderAgent.json on initialization
   - Check logs for: "Loaded Builder Agent flow ID: ..."

### Flow Not Found in Database

**Symptom**: Flow doesn't appear in the Builder Agent folder

**Solution**:
1. Check application startup logs for:
   ```
   Creating/updating builder agent flow
   Builder agent flow created/updated successfully
   ```

2. If you see errors, check:
   - BuilderAgent.json file exists and is valid JSON
   - Database connection is working
   - No permission issues accessing the file

### Folder Not Visible

**Symptom**: Builder Agent folder doesn't appear in the UI

**Solution**:
1. Verify the folder was created:
   ```sql
   SELECT * FROM folder WHERE name = 'Builder Agent';
   ```

2. Check that `user_id` is `NULL` (system folder)

3. Verify the folder is not being filtered in `projects.py`:
   - Only `STARTER_FOLDER_NAME` should be filtered
   - `BUILDER_AGENT_FOLDER_NAME` should be visible

## Technical Details

### Database Schema

**Folder**:
- `id`: UUID (auto-generated)
- `name`: `"Builder Agent"`
- `user_id`: `NULL` (system folder)
- `description`: `"System folder for builder agent flow"`

**Flow**:
- `id`: `01752477-a7b3-4622-8420-36d4a6b81476` (from BuilderAgent.json)
- `name`: `"BuilderAgent"` (from BuilderAgent.json)
- `user_id`: `NULL` (system flow)
- `folder_id`: Builder Agent folder ID
- `data`: Complete flow data from BuilderAgent.json

### Unique Constraints

The database has a unique constraint on `(user_id, name)` for flows. This means:
- Multiple users can have flows with the same name
- System flows (`user_id=NULL`) can coexist with user flows of the same name
- The initialization logic handles migration from user-owned to system-owned flows

## Development Workflow

### Making Changes to Builder Agent

1. **Edit the flow in UI**:
   - Navigate to Builder Agent folder
   - Open BuilderAgent flow
   - Make your changes
   - Test the changes

2. **Export the updated flow**:
   - Click "Export" in the UI
   - Save the JSON file

3. **Update the source file**:
   ```bash
   cp ~/Downloads/BuilderAgent.json src/backend/base/langflow/initial_setup/builder_agent/BuilderAgent.json
   ```

4. **Verify the flow ID is preserved**:
   ```bash
   python -c "import json; data=json.load(open('src/backend/base/langflow/initial_setup/builder_agent/BuilderAgent.json')); print('Flow ID:', data['id'])"
   # Should output: Flow ID: 01752477-a7b3-4622-8420-36d4a6b81476
   ```

5. **Commit and push**:
   ```bash
   git add src/backend/base/langflow/initial_setup/builder_agent/BuilderAgent.json
   git commit -m "feat: update builder agent flow"
   git push
   ```

6. **Deploy**: The updated flow will be automatically loaded on next deployment

### Testing Changes Locally

After updating BuilderAgent.json:

1. **Restart the backend**:
   ```bash
   make backend
   ```

2. **Verify initialization in logs**:
   ```
   Creating/updating builder agent flow
   Updating builder agent flow: 01752477-a7b3-4622-8420-36d4a6b81476
   Builder agent flow created/updated successfully
   ```

3. **Test the agent builder**:
   - Navigate to Agent Builder page in UI
   - Submit a prompt
   - Verify the flow is called correctly

## API Endpoints

### Flow Execution

The builder agent flow is called via the standard Langflow run API:

```
POST /api/v1/run/{flow_id}?stream=true
```

Where `flow_id` is automatically read from BuilderAgent.json.

### Access Control

System flows (`user_id=None`) are accessible through:

- `GET /api/v1/projects/` - Lists all folders including system folders
- `GET /api/v1/projects/{folder_id}` - Access system folders
- `GET /api/v1/flows/{flow_id}` - Access system flows

## Environment Variables Reference

### Required

```bash
# Langflow API URL - Base URL for API calls
LANGFLOW_API_URL=http://localhost:7860
```

### Optional (for development)

```bash
# Database configuration
LANGFLOW_DATABASE_URL=postgresql://postgres:@localhost:5432/studio-test

# Logging
LANGFLOW_LOG_LEVEL=INFO

# Auto-login (development)
LANGFLOW_AUTO_LOGIN=true
```

## Deployment Checklist

Before deploying changes to the Builder Agent:

- [ ] BuilderAgent.json is valid JSON
- [ ] Flow ID in JSON is `01752477-a7b3-4622-8420-36d4a6b81476`
- [ ] All component configurations are correct
- [ ] Environment variables are set in deployment environment
- [ ] Database migrations are up to date
- [ ] Tested locally with `make backend`
- [ ] Verified flow initialization in startup logs

## Related Documentation

- [Agent Builder Integration Overview](./AGENT_BUILDER_INTEGRATION_OVERVIEW.md)
- [Development Guide](./DEVELOPMENT.md)
- Epic: [AUTPE-6043](https://autonomizeai.atlassian.net/browse/AUTPE-6043)

## Support

For issues or questions:
1. Check application logs for initialization errors
2. Verify BuilderAgent.json is valid and has correct ID
3. Ensure database connection is working
4. Check that LANGFLOW_API_URL is set correctly

