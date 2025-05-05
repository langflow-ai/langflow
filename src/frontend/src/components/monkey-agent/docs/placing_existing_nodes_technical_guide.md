# Technical Guide: Placing Existing Nodes on the Canvas Programmatically

This document provides a detailed technical explanation of how to correctly place existing Langflow nodes on the canvas programmatically, ensuring complete compatibility with manually placed nodes.

## 1. Understanding Node Structure in Langflow

Langflow nodes consist of several critical components:

- **Core Node Data**: Base React Flow node properties (id, position, type)
- **Component Configuration**: Node-specific template and properties
- **Connection Points**: Input and output handles for connecting to other nodes
- **Visual Rendering**: How the node appears on the canvas

A node that lacks any of these components, particularly output connections, will not function properly in a workflow.

## 2. Technical Process for Adding a Node

### 2.1 Required Dependencies

```typescript
import { AllNodeType } from "../types/flow";
import { getNodeId, getHandleId } from "../utils/reactflowUtils";
import { useTypesStore } from "../stores/typesStore";
import { getNodeRenderType } from "../utils/utils";
import useFlowStore from "../stores/flowStore";
```

### 2.2 Step-by-Step Node Creation Process

1. **Access Node Templates**
   ```typescript
   const templates = useTypesStore.getState().templates;
   const template = templates[nodeType];
   ```
   This retrieves the template for the specific node type, which contains all the node's configuration.

2. **Generate a Unique Node ID**
   ```typescript
   const nodeId = getNodeId(nodeType);
   ```
   The `getNodeId` utility generates a unique ID using the same pattern that Langflow uses internally.

3. **Create Complete Component Object**
   ```typescript
   const component = {
     ...template,                               // Copy all template properties
     display_name: template.display_name || nodeType,
     template: template.template || {},
     description: template.description || "",
     base_classes: template.base_classes || [],
     documentation: template.documentation || "",
     minimized: false,
     outputs: template.outputs || [             // Critical for connection points
       {
         name: "Message", 
         display_name: "Message",
         types: ["str"],
         selected: "str",
         allows_loop: false
       }
     ],
     input_types: template.input_types || [],
     output_types: template.output_types || ["str"],
     custom_fields: template.custom_fields || {},
     is_input: false,
     is_output: false,
     edited: false
   };
   ```
   
   The `outputs` array is especially critical - it defines the connection points for the node. Without it, the node cannot connect to other nodes in the flow.

4. **Create Node with Proper Structure**
   ```typescript
   const newNode: AllNodeType = {
     id: nodeId,
     type: getNodeRenderType("genericnode"),   // Use Langflow's node type utility
     position: position,
     data: {
       node: component,
       showNode: !component.minimized,         // Controls node expansion
       type: nodeType,
       id: nodeId,
     },
   };
   ```
   
   Note that we use `getNodeRenderType("genericnode")` to ensure the node has the same type as manually created nodes.

5. **Add Node to Canvas Using Langflow's Native Method**
   ```typescript
   const paste = useFlowStore.getState().paste;
   paste({ nodes: [newNode], edges: [] }, position);
   ```
   
   Rather than directly setting nodes, we use Langflow's `paste` function which handles positioning, collisions, and other aspects of node placement.

## 3. Critical Components to Include

For full functionality, ensure these properties are set correctly:

- **outputs**: Defines connection points and their types
- **showNode**: Controls node expansion state
- **type**: Must use `getNodeRenderType` to match Langflow's internal type system
- **template**: Contains the node's parameter configuration

## 4. Common Pitfalls

1. **Missing Outputs**: A node without output connection points cannot be connected to other nodes
2. **Direct Node Setting**: Using `setNodes` directly bypasses Langflow's positioning system
3. **Incomplete Template**: Missing template properties can cause node rendering issues
4. **Wrong Type Assignment**: Not using `getNodeRenderType` can cause inconsistent behavior

## 5. Testing Node Implementation

To verify your implementation is correct, check that:

1. Nodes have the same visual appearance as manually placed ones
2. All connection points (inputs and outputs) are present
3. The node can be connected to other nodes
4. The node can be configured the same as a manually placed node

By following this guide, you'll create nodes programmatically that are identical to those placed manually by users, ensuring a consistent experience in Langflow.
