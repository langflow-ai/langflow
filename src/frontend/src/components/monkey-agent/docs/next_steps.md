# Next Steps: Connecting Monkey Agent Backend to Frontend

## Overview

This document explains how to fully connect the Monkey Agent backend functionality to the frontend components. The backend provides enhanced node registry capabilities and API endpoints that enable programmatic manipulation of flows, while the frontend offers a chat interface for interacting with these capabilities.

## What the Backend Currently Does

The Monkey Agent backend module currently provides several key functionalities:

1. **Enhanced Node Registry**: A more detailed registry of nodes with comprehensive information about inputs, outputs, and connection formats
2. **API Endpoints**: REST endpoints that expose this registry and provide functionality for manipulating flows
3. **Connection Compatibility**: Logic for determining compatible connections between different node types

The main API endpoints are:

- `/api/v1/monkey-agent/registry`: Returns the complete enhanced node registry
- `/api/v1/monkey-agent/registry/node/{node_id}`: Returns details for a specific node
- `/api/v1/monkey-agent/registry/compatibility`: Returns the type compatibility matrix
- `/api/v1/monkey-agent/connection/suggest`: Suggests valid connections between node types
- `/api/v1/monkey-agent/test`: Simple test endpoint

## Connecting to the Frontend

To fully connect the backend capabilities to the frontend, we need to:

1. Create API service functions in the frontend
2. Update the MonkeyAgentChat component to use these services
3. Implement command handling that leverages the backend capabilities

### Step 1: Create API Service Functions

First, create a new API service file for the Monkey Agent:

**File: `/src/frontend/src/controllers/API/monkey-agent.ts`**

```typescript
import { baseURL } from "../constants";
import { FlowType } from "../../types/flow";

// Types for the API responses
export interface EnhancedRegistryResponse {
  nodes: Record<string, NodeRegistryEntry>;
  compatibility: Record<string, string[]>;
}

export interface NodeRegistryEntry {
  id: string;
  name: string;
  description: string;
  inputs: Record<string, InputDefinition>;
  outputs: Record<string, OutputDefinition>;
}

export interface InputDefinition {
  name: string;
  description: string;
  types: string[];
}

export interface OutputDefinition {
  name: string;
  description: string;
  types: string[];
}

export interface ConnectionSuggestion {
  sourceField: string;
  targetField: string;
  compatibility: number;
}

// API client functions
export const getEnhancedRegistry =
  async (): Promise<EnhancedRegistryResponse> => {
    const response = await fetch(`${baseURL}/api/v1/monkey-agent/registry`);
    if (!response.ok) {
      throw new Error(
        `Failed to fetch enhanced registry: ${response.statusText}`,
      );
    }
    return await response.json();
  };

export const getNodeDetails = async (
  nodeId: string,
): Promise<NodeRegistryEntry> => {
  const response = await fetch(
    `${baseURL}/api/v1/monkey-agent/registry/node/${nodeId}`,
  );
  if (!response.ok) {
    throw new Error(`Failed to fetch node details: ${response.statusText}`);
  }
  return await response.json();
};

export const getCompatibilityMatrix = async (): Promise<
  Record<string, string[]>
> => {
  const response = await fetch(
    `${baseURL}/api/v1/monkey-agent/registry/compatibility`,
  );
  if (!response.ok) {
    throw new Error(
      `Failed to fetch compatibility matrix: ${response.statusText}`,
    );
  }
  return await response.json();
};

export const suggestConnections = async (
  sourceId: string,
  targetId: string,
): Promise<ConnectionSuggestion[]> => {
  const response = await fetch(
    `${baseURL}/api/v1/monkey-agent/connection/suggest?source_id=${sourceId}&target_id=${targetId}`,
    {
      method: "POST",
    },
  );
  if (!response.ok) {
    throw new Error(`Failed to suggest connections: ${response.statusText}`);
  }
  return await response.json();
};
```

### Step 2: Update MonkeyAgentChat Component

Now, enhance the MonkeyAgentChat component to use the backend services:

**File: `/src/frontend/src/components/monkey-agent/MonkeyAgentChat.tsx`**

```typescript
// Add imports for the API services
import {
  getEnhancedRegistry,
  suggestConnections,
  NodeRegistryEntry,
} from "../../controllers/API/monkey-agent";

// Add a function to use the enhanced registry for more sophisticated node placement
const addNodeWithEnhancedRegistry = async (
  nodeType: string,
  position = { x: 200, y: 200 },
) => {
  try {
    // Get the full registry from the backend
    const registry = await getEnhancedRegistry();

    // Find matching node type
    const matchedNodeType = Object.keys(registry.nodes).find((key) =>
      key.toLowerCase().includes(nodeType.toLowerCase()),
    );

    if (!matchedNodeType) {
      return {
        success: false,
        message: `Could not find a node type matching "${nodeType}"`,
      };
    }

    // Use the existing node placement tool with the matched type
    return existingNodeTools.processExistingNodeCommand(
      `add ${matchedNodeType}`,
      nodes,
      setNodes,
      onConnect,
    );
  } catch (error) {
    console.error("Error using enhanced registry:", error);
    return {
      success: false,
      message: "Failed to use enhanced registry for node placement.",
    };
  }
};

// Add a function to suggest connections using the backend
const suggestNodeConnections = async (
  sourceNodeId: string,
  targetNodeId: string,
) => {
  try {
    // Get the node types
    const sourceNode = nodes.find((node) => node.id === sourceNodeId);
    const targetNode = nodes.find((node) => node.id === targetNodeId);

    if (!sourceNode || !targetNode) {
      return {
        success: false,
        message: "Could not find the specified nodes",
      };
    }

    const sourceType = sourceNode.data.type;
    const targetType = targetNode.data.type;

    // Get connection suggestions from the backend
    const suggestions = await suggestConnections(sourceType, targetType);

    if (suggestions.length === 0) {
      return {
        success: false,
        message: `No compatible connections found between ${sourceType} and ${targetType}`,
      };
    }

    // Use the best suggestion to connect nodes
    const bestSuggestion = suggestions[0];

    const connection = {
      source: sourceNodeId,
      sourceHandle: existingNodeTools.createSourceHandle(
        sourceNodeId,
        bestSuggestion.sourceField,
      ),
      target: targetNodeId,
      targetHandle: existingNodeTools.createTargetHandle(
        targetNodeId,
        bestSuggestion.targetField,
      ),
    };

    onConnect(connection);

    return {
      success: true,
      message: `Connected ${sourceType} to ${targetType} using ${bestSuggestion.sourceField} → ${bestSuggestion.targetField}`,
    };
  } catch (error) {
    console.error("Error suggesting connections:", error);
    return {
      success: false,
      message: "Failed to suggest connections between nodes.",
    };
  }
};

// Update the handleSendMessage function to use the new backend-powered functions
const handleSendMessage = async () => {
  if (!currentMessage.trim() || loading) return;

  // Add user message to chat
  const userMessage = { role: "user" as const, content: currentMessage };
  setMessages((prevMessages) => [...prevMessages, userMessage]);
  setCurrentMessage("");
  setLoading(true);

  try {
    let result;

    // Check for enhanced commands that use the backend
    if (
      currentMessage.toLowerCase().includes("connect") &&
      currentMessage.includes("to")
    ) {
      // Extract node names or IDs from the message
      // This is a simplified example - real implementation would need more sophisticated parsing
      const parts = currentMessage.split("connect")[1].split("to");
      const sourceNodeId = parts[0].trim();
      const targetNodeId = parts[1].trim();

      result = await suggestNodeConnections(sourceNodeId, targetNodeId);
    }
    // Check for adding nodes using the enhanced registry
    else if (
      currentMessage.toLowerCase().includes("add") ||
      currentMessage.toLowerCase().includes("create")
    ) {
      const nodeType = currentMessage.split(/add|create/i)[1].trim();
      result = await addNodeWithEnhancedRegistry(nodeType, { x: 200, y: 200 });
    }
    // Default to existing node placement if no enhanced commands matched
    else {
      result = existingNodeTools.processExistingNodeCommand(
        currentMessage,
        nodes,
        setNodes,
        onConnect,
      );
    }

    // Add response to chat
    setMessages((prevMessages) => [
      ...prevMessages,
      { role: "assistant" as const, content: result.message },
    ]);
  } catch (error) {
    console.error("Error processing message:", error);

    // Fallback response if there's an error
    setMessages((prevMessages) => [
      ...prevMessages,
      {
        role: "assistant" as const,
        content: "I'm sorry, I encountered an error processing your request.",
      },
    ]);
  } finally {
    setLoading(false);
  }
};
```

### Step 3: Update Registry Connection in enhanced-registry-test.ts

Fix the variable naming issue in this file to use it properly with the backend:

**File: `/src/frontend/src/components/monkey-agent/demo/enhanced-registry-test.ts`**

```typescript
// Fix the import and variable naming
import { useTypesStore } from "../../../stores/typesStore";
import useFlowStore from "../../../stores/flowStore";
import { produce } from "immer";
import {
  scapeJSONParse,
  scapeJSONStringify,
} from "../../../utils/reactflowUtils";

// Fix the function to use the store properly
function addNodeToCanvas(nodeType: string, position: { x: number; y: number }) {
  const typesStore = useTypesStore.getState();
  const flowStoreState = useFlowStore.getState();

  console.log(`Adding node: ${nodeType}`);

  // ... rest of the function ...
}

// Fix the other functions similarly
function connectNodes(
  sourceNodeId: string,
  sourceNodeType: string,
  sourceField: string,
  sourceOutputTypes: string[],
  targetNodeId: string,
  targetField: string,
  targetInputTypes: string[],
) {
  const flowStoreState = useFlowStore.getState();

  // ... rest of the function ...
}
```

### Step 4: Create a Backend API Testing Utility

To help test and debug the backend-frontend connection, create a test utility component:

**File: `/src/frontend/src/components/monkey-agent/demo/ApiTester.tsx`**

```tsx
import React, { useState, useEffect } from "react";
import {
  getEnhancedRegistry,
  getNodeDetails,
  getCompatibilityMatrix,
  suggestConnections,
} from "../../../controllers/API/monkey-agent";

export default function ApiTester() {
  const [registry, setRegistry] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const fetchRegistry = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await getEnhancedRegistry();
      setRegistry(data);
      console.log("Enhanced registry:", data);
    } catch (err) {
      setError(err.message);
      console.error("Error fetching registry:", err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="rounded-lg border p-4">
      <h2 className="mb-4 text-lg font-bold">Monkey Agent API Tester</h2>

      <div className="flex flex-col space-y-4">
        <button
          onClick={fetchRegistry}
          className="rounded-md bg-blue-600 px-4 py-2 text-white hover:bg-blue-700"
          disabled={loading}
        >
          {loading ? "Loading..." : "Fetch Enhanced Registry"}
        </button>

        {error && (
          <div className="rounded border border-red-500 bg-red-100 p-2 text-red-700">
            Error: {error}
          </div>
        )}

        {registry && (
          <div className="mt-4">
            <h3 className="text-md font-bold">Registry Data:</h3>
            <pre className="max-h-60 overflow-auto rounded bg-gray-100 p-2">
              {JSON.stringify(registry, null, 2)}
            </pre>
          </div>
        )}
      </div>
    </div>
  );
}
```

## Common Issues and Debugging

When connecting the frontend and backend, you may encounter these common issues:

1. **CORS Errors**: Ensure the backend properly handles CORS for local development
2. **API Path Mismatches**: Double check that the frontend paths match exactly with the backend routes
3. **Data Format Issues**: Ensure the data structures match between frontend and backend

### Adding CORS Support in the Backend

If you encounter CORS issues, add this middleware to your FastAPI app:

**File: `/src/backend/langflow/api/middleware.py`**

```python
from fastapi.middleware.cors import CORSMiddleware

def add_cors_middleware(app):
    """Add CORS middleware to the app"""
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # For development - restrict in production
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
```

## Testing Your Integration

To test the integration:

1. Start both backend and frontend servers
2. Try using the chat interface with commands like:
   - "Add a text input node"
   - "Connect text input to OpenAI model"
   - "Show me the node registry"
3. Check the browser console for any errors
4. Use the API Tester component to directly test backend endpoints

## Conclusion

By following these steps, you'll have a fully functional Monkey Agent with both frontend and backend integration. The enhanced registry will provide smarter node manipulation capabilities, and the API endpoints will enable more sophisticated flow management from the chat interface.

Future enhancements could include:

- Natural language processing for more flexible command interpretation
- Flow analysis and suggestion capabilities
- Automated flow generation based on user requirements
