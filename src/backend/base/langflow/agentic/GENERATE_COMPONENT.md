# Generate Component

**Feature Status:** In Development
**Last Updated:** January 2025

## Overview

Generate Component is an AI-powered feature that allows users to create Langflow components through natural language prompts. It uses Claude Sonnet 4.5 (Anthropic) to generate Python component code, validates the generated code, and allows users to add the components directly to their flow canvas.

## Architecture

### Backend

The backend is implemented as a FastAPI router located at:
```
src/backend/base/langflow/agentic/api/router.py
```

**API Endpoints:**
- `GET /api/v1/generate-component/check-config` - Checks if ANTHROPIC_API_KEY is configured
- `POST /api/v1/generate-component/prompt` - Executes the component creation flow

**Key Functions:**
- `check_anthropic_api_key()` - Validates API key from global variables or environment
- `execute_flow_file()` - Executes a flow JSON file with user context
- `execute_flow_with_validation()` - Executes flow with automatic code validation and retry logic
- `validate_component_code()` - Validates generated Python code by attempting to create the class
- `extract_python_code()` - Extracts Python code blocks from markdown responses

**Flow Execution:**
The feature uses a pre-built flow located at:
```
src/backend/base/langflow/agentic/flows/ComponentCreation.json
```

This flow uses an Agent component with Claude Sonnet 4.5 to generate component code based on user prompts.

**Validation Loop:**
When the AI generates component code, the backend:
1. Extracts Python code from the markdown response
2. Validates the code using `create_class()` from lfx
3. If validation fails, sends the error back to the AI for correction
4. Retries up to 3 times (configurable via `MAX_VALIDATION_RETRIES`)
5. Returns validation status and component code to the frontend

### Frontend

**Component Location:**
```
src/frontend/src/components/core/generateComponent/
├── index.tsx                       # Main component (GenerateComponent)
├── generate-component-terminal.tsx # Terminal UI component (GenerateComponentTerminal)
└── types.ts                        # TypeScript type definitions
```

**State Management:**
```
src/frontend/src/stores/generateComponentStore.ts  # Zustand store for terminal state
```

**API Hooks:**
```
src/frontend/src/controllers/API/queries/generate-component/
├── index.ts
├── use-get-generate-component-config.ts   # GET /generate-component/check-config
└── use-post-generate-component-prompt.ts  # POST /generate-component/prompt
```

**Additional Hooks Used:**
- `useAddComponent` - Adds validated component to the canvas
- `useAddFlow` - Saves component to sidebar ("Saved" section)
- `usePostValidateComponentCode` - Validates component code before adding/saving

**URL Constants:**
Located in `src/frontend/src/controllers/API/helpers/constants.ts`:
- `GENERATE_COMPONENT_PROMPT: "generate-component/prompt"`
- `GENERATE_COMPONENT_CHECK_CONFIG: "generate-component/check-config"`

### User Interface

**Access:**
- Button located in the sidebar footer, in first position
- Click "Generate component" button to open the terminal

**Terminal Features:**
- Resizable terminal panel (200px - 600px height)
- Command history with arrow key navigation (stored in sessionStorage)
- Multi-line input with auto-resize textarea
- Loading indicator showing model name (Claude Sonnet 4.5) during AI processing
- Validation badges (Valid/Invalid) for generated components
- Configurable max retries (0-5) in the terminal header
- Model name displayed in the terminal header

**Terminal Commands:**
- `MAX_RETRIES=<0-5>` - Set validation retry attempts
- `HELP` or `?` - Show help message with available commands
- `CLEAR` - Clear terminal history

Any other text is treated as a prompt to generate a component.

**Component Result Actions:**
When a valid component is generated, users can:
1. **View Code** (`<>` icon) - Opens a read-only code modal
2. **Download** (download icon) - Downloads the component as a `.py` file
3. **Save to Sidebar** (save icon) - Saves the component to the "Saved" section in the sidebar for reuse across flows
4. **Add to Canvas** (`+` icon) - Validates and adds the component to the current flow

## Configuration Requirements

The feature requires `ANTHROPIC_API_KEY` to be configured either:
1. In environment variables
2. In Langflow Global Variables (Settings > Global Variables)

If not configured, users see an error notification when trying to open the terminal.

## Data Flow

```
User Input (Terminal)
       ↓
POST /generate-component/prompt
       ↓
execute_flow_with_validation()
       ↓
ComponentCreation.json (Agent + Claude Sonnet 4.5)
       ↓
extract_python_code() → validate_component_code()
       ↓
[If invalid: retry with error context, up to 3 times]
       ↓
Response with validation status + component code
       ↓
Frontend displays result with action buttons
       ↓
[User clicks action button]
       ↓
┌─────────────────────────────────────────────────────────┐
│  "Add to Canvas"              │  "Save to Sidebar"      │
│         ↓                     │         ↓               │
│  POST /custom_component/      │  POST /custom_component/│
│        validate               │        validate         │
│         ↓                     │         ↓               │
│  useAddComponent() adds       │  createFlowComponent()  │
│  node to current flow         │         ↓               │
│                               │  useAddFlow() saves to  │
│                               │  "Saved" sidebar section│
└─────────────────────────────────────────────────────────┘
```

## Technical Decisions

### Why user_id is Required
The `ComponentCreation.json` flow uses an Agent component that requires `user_id` to:
1. Access user's global variables (like API keys)
2. Maintain proper component context during execution

The `user_id` is passed through the chain:
`run_prompt_flow()` → `execute_flow_with_validation()` → `execute_flow_file()` → `run_flow()` → `graph.user_id`

### Security Considerations
- API keys are passed via `global_variables`, not environment variables (to avoid global state mutation)
- API keys are never logged (only key names are logged)
- Error messages don't expose internal details

### Code Quality (Following DEVELOPMENT_RULE.md)
- Strong typing with TypeScript and Python type hints
- Constants extracted to avoid magic strings/numbers
- Single source of truth for types (defined in `types.ts`)
- No duplicate type definitions
- Proper error handling with domain-relevant errors

## Files Modified/Created

### Created
- `src/frontend/src/components/core/generateComponent/` (entire folder)
- `src/frontend/src/controllers/API/queries/generate-component/` (entire folder)
- `src/frontend/src/stores/generateComponentStore.ts` - Zustand store for terminal state

### Modified
- `src/frontend/src/controllers/API/helpers/constants.ts` - Added GENERATE_COMPONENT_* URLs
- `src/frontend/src/pages/FlowPage/components/PageComponent/index.tsx` - Import GenerateComponent
- `src/frontend/src/pages/FlowPage/components/flowSidebarComponent/components/sidebarFooterButtons.tsx` - Added Generate component button
- `src/frontend/src/modals/codeAreaModal/index.tsx` - Hide "Check & Save" button in readonly mode
- `src/backend/base/langflow/agentic/api/router.py` - Router prefix, messages, function names, max_retries parameter
- `src/lfx/src/lfx/run/base.py` - Added `user_id` parameter

## Known Issues / TODO

1. **Unit Tests Missing** - Tests should be created for:
   - Backend: `extract_python_code()`, `validate_component_code()`, `execute_flow_with_validation()`
   - Frontend: `GenerateComponentTerminal`, `ComponentResultLine`

2. **Backend Folder Name** - The backend code is still in `/agentic/` folder. Consider renaming to `/generate-component/` for consistency.

## Naming History

The feature was originally named "Vibe Flow", then renamed to "Component Forge", and finally renamed to "Generate Component" to better reflect its purpose and match UI/UX guidelines.

**Renamed items:**
- VibeFlowComponent → ComponentForge → GenerateComponent
- VibeFlowTerminal → ForgeTerminal → GenerateComponentTerminal
- VibeFlowButton → ForgeButton → GenerateComponentButton
- vibe-flow-terminal-history → component-forge-terminal-history → generate-component-terminal-history
- /agentic/* → /forge/* → /generate-component/* (API routes)
- useGetAgenticConfig → useGetForgeConfig → useGetGenerateComponentConfig
- usePostAgenticPrompt → usePostForgePrompt → usePostGenerateComponentPrompt
