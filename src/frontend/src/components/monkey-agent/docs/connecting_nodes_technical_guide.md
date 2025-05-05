# Technical Guide: Connecting Nodes Programmatically in Langflow

This document provides a detailed explanation of how to connect nodes in a Langflow canvas programmatically, ensuring full compatibility with manually created connections.

## 1. Understanding Connection Structure in Langflow

Langflow connections (edges) are complex objects that contain essential metadata about how nodes interact. A connection consists of:

### 1.1 Core Connection Elements

```typescript
{
  source: string,         // ID of the source node
  sourceHandle: string,   // Encoded string representing output handle data
  target: string,         // ID of the target node
  targetHandle: string,   // Encoded string representing input handle data
  data: {                 // Parsed metadata (added by onConnect)
    sourceHandle: object, // Decoded source handle data
    targetHandle: object  // Decoded target handle data
  }
}
```

### 1.2 Handle Encoding

Handles are encoded using a special JSON format where quotes (`"`) are replaced with a special character (`œ`):

```typescript
// Example of an encoded sourceHandle
"{"id":"textinput-abc123","name":"text","output_types":["str"],"dataType":"TextInput"}".replace(/"/g, "œ")
```

This encoding prevents conflicts with JSON parsing in ReactFlow.

## 2. Technical Process for Connecting Nodes

### 2.1 Required Dependencies

```typescript
import { scapedJSONStringfy, scapeJSONParse } from "../utils/reactflowUtils";
import useFlowStore from "../stores/flowStore";
```

### 2.2 Step-by-Step Connection Process

1. **Generate Properly Formatted Handle IDs**

   For the source (output) handle:

   ```typescript
   function createSourceHandle(nodeId: string, outputName: string): string {
     const handleData = {
       id: nodeId,
       name: outputName, // The name of the output
       output_types: ["str"], // The types this output provides
       dataType: "TextInput", // The node type
     };

     return scapedJSONStringfy(handleData);
   }
   ```

   For the target (input) handle:

   ```typescript
   function createTargetHandle(nodeId: string, inputName: string): string {
     const handleData = {
       id: nodeId,
       name: inputName, // The parameter name
       fieldName: inputName, // The field in the template
       dataType: "ChatOpenAI", // The node type
     };

     return scapedJSONStringfy(handleData);
   }
   ```

2. **Create Connection Object**

   ```typescript
   const connection = {
     source: sourceNodeId,
     sourceHandle: createSourceHandle(sourceNodeId, "text"),
     target: targetNodeId,
     targetHandle: createTargetHandle(targetNodeId, "text"),
   };
   ```

3. **Apply the Connection**

   ```typescript
   // Using the flow store's onConnect method
   const onConnect = useFlowStore.getState().onConnect;
   onConnect(connection);
   ```

   The `onConnect` function will:

   - Parse the handle data
   - Validate the connection
   - Add the connection to the flow's edges

## 3. Connection Validation

Langflow validates connections before adding them:

```typescript
isValidConnection(connection, nodes, edges);
```

This function checks:

- Connection doesn't create a cycle
- Data types are compatible
- Connection is between an output and an input handle
- Handles exist on the nodes

## 4. Common Connection Patterns

### 4.1 Text Input → OpenAI

```typescript
// Example: Connecting Text Input to OpenAI
const textNodeId = "textinput-abc123";
const openAINodeId = "chatopenai-def456";

const connection = {
  source: textNodeId,
  sourceHandle: createSourceHandle(textNodeId, "text"),
  target: openAINodeId,
  targetHandle: createTargetHandle(openAINodeId, "text"),
};

onConnect(connection);
```

### 4.2 Multiple Connections

For complex flows, you can create multiple connections in sequence:

```typescript
// Add first connection
onConnect(connection1);

// Add second connection
onConnect(connection2);
```

## 5. Troubleshooting Connection Issues

If connections aren't working:

1. **Verify Node IDs**: Ensure node IDs match exactly what's in the flow
2. **Check Data Types**: Make sure source and target handles have compatible types
3. **Inspect Handle Format**: Verify handles are correctly encoded with `scapedJSONStringfy`
4. **Timing**: Ensure nodes are fully initialized before attempting connections
5. **Flow Store**: Confirm you have access to the correct flow store instance

## 6. Best Practices

1. **Use Delayed Connection**: Add a small delay (e.g., `setTimeout`) after adding nodes before connecting them
2. **Handle Validation**: Check that nodes exist before creating connections
3. **Error Handling**: Provide fallbacks if connections fail
4. **Type Compatibility**: Verify output and input types match before connecting

By following this guide, you can programmatically create connections between nodes that are indistinguishable from manually drawn connections in Langflow.
