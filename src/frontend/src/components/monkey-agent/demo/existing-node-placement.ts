/**
 * Existing Node Placement
 * 
 * This file provides functionality for placing existing Langflow nodes on the canvas
 * using Langflow's native methods for complete compatibility.
 */

import { AllNodeType } from "../../../types/flow";
import { getNodeId } from "../../../utils/reactflowUtils";
import { useTypesStore } from "../../../stores/typesStore";
import { getNodeRenderType } from "../../../utils/utils";
import useFlowStore from "../../../stores/flowStore";

/**
 * Add an existing node type to the canvas using Langflow's exact native method
 */
export const addExistingNode = (
  nodeType: string, 
  position = { x: 200, y: 200 },
  setNodes: (updater: (oldNodes: AllNodeType[]) => AllNodeType[]) => void
) => {
  try {
    // Get templates from types store
    const templates = useTypesStore.getState().templates;
    
    // Log available templates for debugging
    console.log("Available template types:", Object.keys(templates));
    
    // Examine templates to find the OpenAI node with the correct description
    const openAINodes = Object.keys(templates).filter(key => {
      const template = templates[key];
      if (!template) return false;
      
      return template.description && template.description.includes("Generates text using OpenAI");
    });
    
    console.log("Found OpenAI text generation nodes:", openAINodes);
    
    const template = templates[nodeType];
    
    if (!template) {
      console.error(`Template for node type ${nodeType} not found`);
      return null;
    }
    
    // Generate ID using Langflow's native method
    const nodeId = getNodeId(nodeType);
    
    // Create the component object using the template - must include ALL properties
    const component = {
      ...template,                                // Copy all template properties
      display_name: template.display_name || nodeType,
      template: template.template || {},
      description: template.description || "",
      base_classes: template.base_classes || [],
      documentation: template.documentation || "",
      minimized: false,
      // Essential: Include outputs for connection capabilities
      outputs: template.outputs || [
        {
          name: "Message", 
          display_name: "Message",
          types: ["str"],
          selected: "str",
          allows_loop: false
        }
      ],
      // Copy additional required properties
      input_types: template.input_types || [],
      output_types: template.output_types || ["str"],
      custom_fields: template.custom_fields || {},
      is_input: false,
      is_output: false,
      edited: false
    };
    
    // Create node with the exact same structure as Langflow
    const newNode: AllNodeType = {
      id: nodeId,
      type: getNodeRenderType("genericnode"),
      position: position,
      data: {
        node: component,
        showNode: !component.minimized,
        type: nodeType,
        id: nodeId,
      },
    };
    
    // Use Langflow's exact paste method for adding nodes
    const paste = useFlowStore.getState().paste;
    
    // Add node to canvas using Langflow's native paste function
    paste({ nodes: [newNode], edges: [] }, position);
    
    return nodeId;
  } catch (error) {
    console.error("Error adding existing node:", error);
    return null;
  }
};

/**
 * Process a command specifically for placing existing nodes
 */
export const processExistingNodeCommand = (
  message: string,
  nodes: AllNodeType[],
  setNodes: (updater: (oldNodes: AllNodeType[]) => AllNodeType[]) => void,
  onConnect: (connection: any) => void
) => {
  // Command to add a Text Input node
  if (message.toLowerCase().includes('add text input')) {
    const nodeId = addExistingNode("TextInput", { x: 200, y: 200 }, setNodes);
    
    if (nodeId) {
      return {
        success: true,
        message: "I've added a Text Input node to your canvas using Langflow's native system. It's identical to what you'd get by manually placing one.",
        action: "added_node",
        details: { nodeType: "TextInput", nodeId }
      };
    } else {
      return {
        success: false,
        message: "I couldn't add the Text Input node. The node template might not be available.",
        action: "error",
        details: { reason: "template_not_found" }
      };
    }
  }
  
  // Command to add a Chat Input node
  else if (message.toLowerCase().includes('add chat input')) {
    const nodeId = addExistingNode("ChatInput", { x: 200, y: 200 }, setNodes);
    
    if (nodeId) {
      return {
        success: true,
        message: "I've added a Chat Input node to your canvas. This node allows interactive chat input in your flow.",
        action: "added_node",
        details: { nodeType: "ChatInput", nodeId }
      };
    } else {
      return {
        success: false,
        message: "I couldn't add the Chat Input node. The node template might not be available.",
        action: "error",
        details: { reason: "template_not_found" }
      };
    }
  }
  
  // Command to add OpenAI Embeddings node
  else if (message.toLowerCase().includes('add openai embeddings') || 
           message.toLowerCase().includes('add embeddings')) {
    const nodeId = addExistingNode("OpenAIEmbeddings", { x: 200, y: 200 }, setNodes);
    
    if (nodeId) {
      return {
        success: true,
        message: "I've added an OpenAI Embeddings node to your canvas. This node generates vector embeddings for text using OpenAI's models.",
        action: "added_node",
        details: { nodeType: "OpenAIEmbeddings", nodeId }
      };
    } else {
      return {
        success: false,
        message: "I couldn't add the OpenAI Embeddings node. The node template might not be available.",
        action: "error",
        details: { reason: "template_not_found" }
      };
    }
  }
  
  // Command to add OpenAI node (the basic text generation one, not embeddings)
  else if (message.toLowerCase().includes('add openai') && !message.toLowerCase().includes('embeddings')) {
    // Get the templates and data from the types store
    const typesState = useTypesStore.getState();
    const templates = typesState.templates;
    const data = typesState.data;
    
    console.log("Available categories:", Object.keys(data));
    
    // First, try to find the exact node with the specific description
    const openAITextNodes = Object.keys(templates).filter(key => {
      const template = templates[key];
      return template && 
             template.description && 
             template.description.includes("Generates text using OpenAI");
    });
    
    console.log("Found OpenAI text generation nodes:", openAITextNodes);
    
    // Use the specific text generation node if found
    let openAINodeType = "";
    if (openAITextNodes.length > 0) {
      openAINodeType = openAITextNodes[0];
      console.log("Using specific OpenAI text generation node:", openAINodeType);
    }
    // If not found, check for LLMs category
    else if (data["LLMs"]) {
      const llmNodes = Object.keys(data["LLMs"]);
      console.log("Available LLM nodes:", llmNodes);
      
      // First try to find the exact "OpenAI" node (not ChatOpenAI, etc.)
      if (llmNodes.includes("OpenAI")) {
        openAINodeType = "OpenAI";
      } 
      // Next try other variants that contain "OpenAI" in the name but EXCLUDE embeddings
      else {
        const openAIVariants = llmNodes.filter(node => 
          node.includes("OpenAI") && 
          !node.toLowerCase().includes("embeddings") && 
          !node.toLowerCase().includes("embedding")
        );
        
        if (openAIVariants.length > 0) {
          // Use the first variant found
          openAINodeType = openAIVariants[0];
        }
      }
    }
    
    console.log("Selected OpenAI node type:", openAINodeType);
    
    // Verify the selected node is indeed for text generation (not embeddings)
    if (openAINodeType && templates[openAINodeType]) {
      const template = templates[openAINodeType];
      
      // Double-check this isn't an embeddings node
      if (template.description && 
          (template.description.toLowerCase().includes("embeddings") || 
           template.description.toLowerCase().includes("embedding"))) {
        console.log("Rejecting node as it appears to be an embeddings node:", template.description);
        openAINodeType = ""; // Reset and try again
      }
    }
    
    // If we found a valid node type, add it to the canvas
    if (openAINodeType && templates[openAINodeType]) {
      const nodeId = addExistingNode(openAINodeType, { x: 200, y: 200 }, setNodes);
      
      if (nodeId) {
        return {
          success: true,
          message: `I've added the ${templates[openAINodeType].display_name || openAINodeType} node to your canvas.`,
          action: "added_node",
          details: { nodeType: openAINodeType, nodeId }
        };
      }
    }
    
    // If all attempts fail, show available LLM nodes
    const llmNodes = data["LLMs"] ? Object.keys(data["LLMs"]) : [];
    return {
      success: false,
      message: "I couldn't find the OpenAI text generation node. Available LLM nodes: " + 
               llmNodes.join(", "),
      action: "error",
      details: { reason: "node_not_found", availableNodes: llmNodes }
    };
  }
  
  // Command to connect existing nodes
  else if (message.toLowerCase().includes('connect existing nodes') || 
           message.toLowerCase().includes('connect nodes')) {
    
    // Get IDs of nodes to connect
    let sourceNodeId = message.match(/source:?\s*([a-zA-Z0-9-_]+)/i)?.[1];
    let targetNodeId = message.match(/target:?\s*([a-zA-Z0-9-_]+)/i)?.[1];
    
    // If no specific node IDs are provided, try to find a TextInput node and an OpenAI node
    if (!sourceNodeId || !targetNodeId) {
      console.log("No specific node IDs provided, searching for TextInput and OpenAI nodes");
      
      // Find a TextInput node
      const textInputNodes = nodes.filter(node => 
        node.data.type === "TextInput" || 
        (node.data.node?.display_name === "Text Input")
      );
      
      // Find an OpenAI node
      const openAINodes = nodes.filter(node => 
        node.data.type === "OpenAI" || 
        node.data.type?.includes("OpenAI") ||
        (node.data.node?.description?.includes("Generates text using OpenAI"))
      );
      
      console.log("Found potential nodes to connect:", {
        textInputNodes: textInputNodes.map(n => n.id),
        openAINodes: openAINodes.map(n => n.id)
      });
      
      if (textInputNodes.length > 0 && openAINodes.length > 0) {
        sourceNodeId = textInputNodes[0].id;
        targetNodeId = openAINodes[0].id;
      }
    }
    
    if (!sourceNodeId || !targetNodeId) {
      return {
        success: false,
        message: "I couldn't find suitable nodes to connect. Please specify the node IDs or ensure you have a Text Input and OpenAI node in your flow.",
        action: "error",
        details: { reason: "nodes_not_found" }
      };
    }
    
    // Find the nodes
    const sourceNode = nodes.find(node => node.id === sourceNodeId);
    const targetNode = nodes.find(node => node.id === targetNodeId); 
    
    if (!sourceNode || !targetNode) {
      return {
        success: false,
        message: `I couldn't find the specified nodes. Make sure they exist in the current flow.`,
        action: "error",
        details: { sourceNodeId, targetNodeId }
      };
    }
    
    // Print detailed info about the nodes we're connecting
    console.log("Source node data:", {
      id: sourceNode.id,
      type: sourceNode.data.type,
      displayName: sourceNode.data.node?.display_name,
      outputs: sourceNode.data.node?.outputs
    });
    
    console.log("Target node data:", {
      id: targetNode.id,
      type: targetNode.data.type,
      displayName: targetNode.data.node?.display_name,
      templateFields: targetNode.data.node?.template ? Object.keys(targetNode.data.node.template) : []
    });
    
    // Based on the working screenshot, we know the connection is:
    // - TextInput "Message" output to OpenAI "Input" field
    const sourceOutputField = "text";  // Exact casing from the screenshot
    let targetInputField = "input_value";      // Exact casing from the screenshot
    
    console.log("Using source output field:", sourceOutputField);
    console.log("Using target input field:", targetInputField);
    
    // Check if the target has the 'input' field
    if (targetNode.data.node?.template && !targetNode.data.node.template[targetInputField]) {
      console.warn(`Target node does not have '${targetInputField}' field. Available fields:`, 
        Object.keys(targetNode.data.node.template));
      
      // Try to find a suitable alternative input field
      const inputFieldPriority = ["input", "text", "message", "content", "prompt", "question"];
      for (const field of inputFieldPriority) {
        if (targetNode.data.node.template[field]) {
          console.log(`Using alternative field '${field}' instead of '${targetInputField}'`);
          targetInputField = field;
          break;
        }
      }
    }
    
    // Connect the nodes with explicit fields
    const connected = connectExistingNodes(
      sourceNodeId,
      sourceOutputField,
      targetNodeId,
      targetInputField,
      nodes,
      onConnect
    );
    
    if (connected) {
      return {
        success: true,
        message: `I've connected the ${sourceNode.data.node?.display_name || "source"} node's text output to the ${targetNode.data.node?.display_name || "target"} node's input_value field.`,
        action: "connected_nodes",
        details: { sourceNodeId, targetNodeId, sourceField: sourceOutputField, targetField: targetInputField }
      };
    } else {
      return {
        success: false,
        message: "I wasn't able to connect the nodes. Please try connecting them manually.",
        action: "error",
        details: { reason: "connection_failed", sourceField: sourceOutputField, targetField: targetInputField }
      };
    }
  }
  
  // Command to add Text Input + OpenAI and connect them
  else if (message.toLowerCase().includes('add text and openai') || 
           message.toLowerCase().includes('connect text to openai')) {
    
    // First add Text Input
    const textNodeId = addExistingNode("TextInput", { x: 200, y: 200 }, setNodes);
    
    if (!textNodeId) {
      return {
        success: false,
        message: "I couldn't add the Text Input node. The node template might not be available.",
        action: "error",
        details: { reason: "template_not_found" }
      };
    }
    
    // Get templates from the types store
    const templates = useTypesStore.getState().templates;
    const data = useTypesStore.getState().data;
    
    console.log("Available categories:", Object.keys(data));
    
    // First, try to find the exact node with the specific description
    const openAITextNodes = Object.keys(templates).filter(key => {
      const template = templates[key];
      return template && 
             template.description && 
             template.description.includes("Generates text using OpenAI");
    });
    
    console.log("Found OpenAI text generation nodes:", openAITextNodes);
    
    // Use the specific text generation node if found
    let openAINodeType = "";
    if (openAITextNodes.length > 0) {
      openAINodeType = openAITextNodes[0];
      console.log("Using specific OpenAI text generation node:", openAINodeType);
    }
    // If not found, check for LLMs category
    else if (data["LLMs"]) {
      const llmNodes = Object.keys(data["LLMs"]);
      console.log("Available LLM nodes:", llmNodes);
      
      // First try to find the exact "OpenAI" node (not ChatOpenAI, etc.)
      if (llmNodes.includes("OpenAI")) {
        openAINodeType = "OpenAI";
      } 
      // Next try other variants that contain "OpenAI" in the name but EXCLUDE embeddings
      else {
        const openAIVariants = llmNodes.filter(node => 
          node.includes("OpenAI") && 
          !node.toLowerCase().includes("embeddings") && 
          !node.toLowerCase().includes("embedding")
        );
        
        if (openAIVariants.length > 0) {
          // Use the first variant found
          openAINodeType = openAIVariants[0];
        }
      }
    }
    
    console.log("Selected OpenAI node type for connection:", openAINodeType);
    
    // Verify the selected node is indeed for text generation (not embeddings)
    if (openAINodeType && templates[openAINodeType]) {
      const template = templates[openAINodeType];
      
      // Double-check this isn't an embeddings node
      if (template.description && 
          (template.description.toLowerCase().includes("embeddings") || 
           template.description.toLowerCase().includes("embedding"))) {
        console.log("Rejecting node as it appears to be an embeddings node:", template.description);
        openAINodeType = ""; // Reset and try again
      }
    }
    
    // If we found a valid node type, add it to the canvas
    if (openAINodeType && templates[openAINodeType]) {
      const openAINodeId = addExistingNode(openAINodeType, { x: 500, y: 200 }, setNodes);
      
      if (openAINodeId) {
        // Wait for nodes to be added to DOM and react-flow state
        setTimeout(() => {
          // We need to connect the output of TextInput to an input of the OpenAI node
          const sourceNode = nodes.find(node => node.id === textNodeId);
          const targetNode = nodes.find(node => node.id === openAINodeId);
          
          if (sourceNode && targetNode) {
            // Examine nodes for debugging
            console.log("Source node:", sourceNode);
            console.log("Target node:", targetNode);
            
            // Get the actual output field from TextInput node
            const sourceTemplate = sourceNode.data.node;
            const sourceOutputs = sourceTemplate?.outputs;
            console.log("Source node outputs:", sourceOutputs);
            
            // Default output name is "text", but check the actual outputs
            let sourceOutputName = "text";
            if (sourceOutputs && sourceOutputs.length > 0) {
              sourceOutputName = sourceOutputs[0].name || "text";
            }
            console.log("Using source output:", sourceOutputName);
            
            // Find the input field for the target node by examining the template
            const targetTemplate = targetNode.data.node?.template;
            
            // Log all the template fields for debugging
            console.log("Target node template fields:", Object.keys(targetTemplate));
            
            // Input field priority - specific to OpenAI models from examining the data structure
            const inputFieldPriority = ["input_value", "text", "message", "content", "prompt", "question"];
            let inputFieldName = "";
            
            // Look for fields that exist in the template
            for (const field of inputFieldPriority) {
              if (targetTemplate[field]) {
                inputFieldName = field;
                break;
              }
            }
            
            // If no match found, use the first template key
            if (!inputFieldName) {
              const templateKeys = Object.keys(targetTemplate);
              inputFieldName = templateKeys.length > 0 ? templateKeys[0] : "input_value";
            }
            
            console.log("Using input field:", inputFieldName);
            
            // Create connection object with direct parameters to match getHandleId expectations
            const connection = {
              source: textNodeId,
              sourceHandle: createSourceHandle(textNodeId, sourceOutputName),
              target: openAINodeId,
              targetHandle: createTargetHandle(openAINodeId, inputFieldName)
            };
            
            console.log("Connection object:", connection);
            
            // Connect the nodes
            onConnect(connection);
            
            console.log("onConnect called - connection should be established");
            
            return {
              success: true,
              message: `I've added a Text Input node and ${openAINodeType} node to your canvas, and connected them. The Text Input will feed directly into the OpenAI model.`,
              action: "added_connected_nodes",
              details: { sourceNodeId: textNodeId, targetNodeId: openAINodeId }
            };
          } else {
            console.error("Couldn't find source or target node for connection");
          }
        }, 500); // Short delay to ensure nodes are fully initialized
        
        return {
          success: true,
          message: `I'm adding a Text Input node and ${openAINodeType} node to your canvas, and connecting them...`,
          action: "adding_connected_nodes",
          details: { sourceNodeId: textNodeId, targetNodeId: openAINodeId }
        };
      } else {
        return {
          success: false,
          message: "I couldn't find the OpenAI text generation node to connect with.",
          action: "error",
          details: { reason: "node_not_found" }
        };
      }
    }
  }
  
  // Command to add two nodes and connect them using the enhanced registry knowledge
  else if (message.toLowerCase().includes('add document to embeddings flow') || 
           message.toLowerCase().includes('create document embedding pipeline')) {
    // First add Document Loader
    const documentLoaderPosition = { x: 100, y: 200 };
    const documentLoaderId = addExistingNode("DocumentLoader", documentLoaderPosition, setNodes);
    
    if (!documentLoaderId) {
      return {
        success: false,
        message: "I couldn't add the Document Loader node. The node template might not be available.",
        action: "error",
        details: { reason: "template_not_found" }
      };
    }
    
    // Next add OpenAI Embeddings
    const embeddingsPosition = { x: 500, y: 200 };
    const embeddingsId = addExistingNode("OpenAIEmbeddings", embeddingsPosition, setNodes);
    
    if (!embeddingsId) {
      return {
        success: false,
        message: "I couldn't add the OpenAI Embeddings node. The node template might not be available.",
        action: "error",
        details: { reason: "template_not_found" }
      };
    }
    
    // Connect Document Loader to OpenAI Embeddings
    const connection = connectExistingNodes(
      documentLoaderId,
      "text",
      embeddingsId,
      "input_value",
      nodes,
      onConnect
    );
    
    if (!connection) {
      return {
        success: false,
        message: "I wasn't able to connect the nodes. Please try connecting them manually.",
        action: "error",
        details: { reason: "connection_failed" }
      };
    }
    
    return {
      success: true,
      message: "I've added a Document Loader node and an OpenAI Embeddings node to your canvas, and connected them.",
      action: "added_connected_nodes",
      details: { sourceNodeId: documentLoaderId, targetNodeId: embeddingsId }
    };
  }
  
  // Enhanced Registry Commands - Using knowledge from the backend registry
  else if (message.toLowerCase().includes("document") && message.toLowerCase().includes("embedding")) {
    console.log("Starting document embeddings flow with enhanced registry knowledge");
    
    // Find document loader template
    const documentLoaderType = "DocumentLoader";
    const documentTemplate = findNodeByTypeDescription(documentLoaderType);
    if (!documentTemplate) {
      return {
        success: false,
        message: `I couldn't find the ${documentLoaderType} template.`,
        action: "error",
        details: { reason: "template_not_found" }
      };
    }
    
    // Find embeddings template
    const embeddingsType = "OpenAIEmbeddings";
    const embeddingsTemplate = findNodeByTypeDescription(embeddingsType);
    if (!embeddingsTemplate) {
      return {
        success: false,
        message: `I couldn't find the ${embeddingsType} template.`,
        action: "error",
        details: { reason: "template_not_found" }
      };
    }
    
    console.log("Found document loader:", documentTemplate.display_name);
    console.log("Found embeddings:", embeddingsTemplate.display_name);
    
    // Add document loader node
    const documentPosition = { x: 100, y: 200 };
    const documentNodeId = addExistingNode(documentLoaderType, documentPosition, setNodes);
    
    if (!documentNodeId) {
      return {
        success: false,
        message: `I couldn't add the ${documentLoaderType} node.`,
        action: "error",
        details: { reason: "node_creation_failed" }
      };
    }
    
    // Add embeddings node
    const embeddingsPosition = { x: 500, y: 200 };
    const embeddingsNodeId = addExistingNode(embeddingsType, embeddingsPosition, setNodes);
    
    if (!embeddingsNodeId) {
      return {
        success: false,
        message: `I couldn't add the ${embeddingsType} node.`,
        action: "error",
        details: { reason: "node_creation_failed" }
      };
    }
    
    console.log("Added document loader node:", documentNodeId);
    console.log("Added embeddings node:", embeddingsNodeId);
    
    // Wait to ensure nodes are properly initialized
    setTimeout(() => {
      // We need to connect the output of DocumentLoader to an input of the OpenAIEmbeddings node
      const sourceNode = nodes.find(node => node.id === documentNodeId);
      const targetNode = nodes.find(node => node.id === embeddingsNodeId);
      
      if (sourceNode && targetNode) {
        // Examine nodes for debugging
        console.log("Source node:", sourceNode);
        console.log("Target node:", targetNode);
        
        // Get the actual output field from DocumentLoader node
        const sourceTemplate = sourceNode.data.node;
        const sourceOutputs = sourceTemplate?.outputs;
        console.log("Source node outputs:", sourceOutputs);
        
        // Default output name is "text", but check the actual outputs
        let sourceOutputName = "text";
        if (sourceOutputs && sourceOutputs.length > 0) {
          sourceOutputName = sourceOutputs[0].name || "text";
        }
        console.log("Using source output:", sourceOutputName);
        
        // Find the input field for the target node by examining the template
        const targetTemplate = targetNode.data.node?.template;
        
        // Log all the template fields for debugging
        console.log("Target node template fields:", Object.keys(targetTemplate));
        
        // Input field priority - specific to OpenAI models from examining the data structure
        const inputFieldPriority = ["input_value", "text", "message", "content", "prompt", "question"];
        let inputFieldName = "";
        
        // Look for fields that exist in the template
        for (const field of inputFieldPriority) {
          if (targetTemplate[field]) {
            inputFieldName = field;
            break;
          }
        }
        
        // If no match found, use the first template key
        if (!inputFieldName) {
          const templateKeys = Object.keys(targetTemplate);
          inputFieldName = templateKeys.length > 0 ? templateKeys[0] : "input_value";
        }
        
        console.log("Using input field:", inputFieldName);
        
        // Create connection object with direct parameters to match getHandleId expectations
        const connection = {
          source: documentNodeId,
          sourceHandle: createSourceHandle(documentNodeId, sourceOutputName),
          target: embeddingsNodeId,
          targetHandle: createTargetHandle(embeddingsNodeId, inputFieldName)
        };
        
        console.log("Connection object:", connection);
        
        // Connect the nodes
        onConnect(connection);
        
        console.log("onConnect called - connection should be established");
        
        return {
          success: true,
          message: `I've added a Document Loader node and an OpenAI Embeddings node to your canvas, and connected them. The Document Loader will feed directly into the OpenAI Embeddings model.`,
          action: "added_connected_nodes",
          details: { sourceNodeId: documentNodeId, targetNodeId: embeddingsNodeId }
        };
      } else {
        console.error("Couldn't find source or target node for connection");
      }
    }, 500); // Short delay to ensure nodes are fully initialized
    
    return {
      success: true,
      message: `I'm adding a Document Loader node and an OpenAI Embeddings node to your canvas, and connecting them...`,
      action: "adding_connected_nodes",
      details: { sourceNodeId: documentNodeId, targetNodeId: embeddingsNodeId }
    };
  }
  
  // Default response for unrecognized commands
  return {
    success: false,
    message: "I understand you want to: \"" + message + "\". Currently, I can add these nodes: Text Input, Chat Input, OpenAI, or OpenAI Embeddings. Try saying \"add text input\", \"add chat input\", \"add openai\", \"add openai embeddings\", or \"connect text to openai\".",
    action: "unrecognized_command",
    details: null
  };
};

/**
 * Finds a node template by type or description
 * Uses a cascading approach to find the closest match
 */
function findNodeByTypeDescription(typeDescription: string) {
  const typesStore = useTypesStore.getState();
  const templates = typesStore.templates;
  
  console.log(`Looking for node template: ${typeDescription}`);
  
  // 1. Direct match by template key
  if (templates[typeDescription]) {
    console.log(`Found exact template match for ${typeDescription}`);
    return templates[typeDescription];
  }
  
  // 2. Search by node type name match (case-insensitive)
  const lowerTypeDesc = typeDescription.toLowerCase();
  const templateValues = Object.values(templates);
  
  // Common mappings for node types
  const typeNameMappings: {[key: string]: string[]} = {
    "documentloader": ["DocumentLoader", "WebBaseLoader", "PDFLoader"],
    "openaiembeddings": ["OpenAIEmbeddings"],
    "textsplitter": ["RecursiveCharacterTextSplitter"],
    "vectorstore": ["Chroma", "FAISS"],
    "textinput": ["TextInput"],
    "openai": ["OpenAI", "ChatOpenAI"],
  };
  
  // Check if we have a specific mapping for this type
  const lowerKey = lowerTypeDesc.replace(/\s+/g, "");
  if (typeNameMappings[lowerKey]) {
    for (const nodeName of typeNameMappings[lowerKey]) {
      if (templates[nodeName]) {
        console.log(`Found mapped template match for ${typeDescription}: ${nodeName}`);
        return templates[nodeName];
      }
    }
  }
  
  // 3. Fuzzy match by display name
  const matchingTemplates = templateValues.filter(template => 
    template.display_name?.toLowerCase().includes(lowerTypeDesc)
  );
  
  if (matchingTemplates.length > 0) {
    console.log(`Found ${matchingTemplates.length} display name matches for ${typeDescription}`);
    return matchingTemplates[0];
  }
  
  // 4. Fuzzy match by description
  const descriptionMatches = templateValues.filter(template => 
    template.description?.toLowerCase().includes(lowerTypeDesc)
  );
  
  if (descriptionMatches.length > 0) {
    console.log(`Found ${descriptionMatches.length} description matches for ${typeDescription}`);
    return descriptionMatches[0];
  }
  
  console.log(`No template found for ${typeDescription}`);
  return null;
}

/**
 * Connect existing nodes in the flow 
 */
function connectExistingNodes(
  sourceNodeId: string,
  sourceOutputField: string,
  targetNodeId: string,
  targetInputField: string,
  nodes: AllNodeType[],
  onConnect: (connection: any) => void
): boolean {
  try {
    // Find the nodes
    const sourceNode = nodes.find(node => node.id === sourceNodeId);
    const targetNode = nodes.find(node => node.id === targetNodeId);
    
    if (!sourceNode || !targetNode) {
      console.error("Could not find source or target node for connection", {
        sourceNodeId,
        targetNodeId, 
        nodesFound: nodes.map(n => n.id)
      });
      return false;
    }
    
    // Examine nodes more closely
    console.log(`Connecting node ${sourceNode.id} to ${targetNode.id}`);
    console.log("Source node:", sourceNode);
    console.log("Target node:", targetNode);
    
    // Get output type from source node
    let outputType = "str";
    const sourceNodeOutputs = sourceNode.data.node?.outputs;
    if (sourceNodeOutputs && sourceNodeOutputs.length > 0) {
      const output = sourceNodeOutputs.find(o => o.name === sourceOutputField);
      if (output && output.selected) {
        outputType = output.selected;
      } else if (output && output.types && output.types.length > 0) {
        outputType = output.types[0];
      }
    }
    
    // Get input type from target node
    let inputType = "str";
    const targetInputTypes = targetNode.data.node?.template?.[targetInputField]?.input_types;
    if (targetInputTypes && targetInputTypes.length > 0) {
      inputType = targetInputTypes[0];
    }
    
    console.log(`Source output type: ${outputType}, Target input type: ${inputType}`);
    
    // Check for compatibility (may need more sophisticated checking)
    if (outputType !== inputType && 
        !["str", "text", "message", "flow", "any"].includes(inputType)) {
      console.error(`Incompatible types: ${outputType} -> ${inputType}`);
      return false;
    }
    
    // Check for existing connections to avoid duplicates
    const edges = useFlowStore.getState().edges;
    const existingConnection = edges.find(edge => 
      edge.source === sourceNodeId && 
      edge.target === targetNodeId &&
      (edge.data?.sourceHandle?.name === sourceOutputField || 
       edge.sourceHandle?.includes(sourceOutputField)) &&
      (edge.data?.targetHandle?.name === targetInputField ||
       edge.targetHandle?.includes(targetInputField))
    );
    
    if (existingConnection) {
      console.log("Connection already exists:", existingConnection);
      return true; // Return true since the connection exists
    }
    
    // Create connection object with proper handle formatting
    const connection = {
      source: sourceNodeId,
      sourceHandle: createSourceHandle(sourceNodeId, sourceOutputField),
      target: targetNodeId,
      targetHandle: createTargetHandle(targetNodeId, targetInputField)
    };
    
    console.log("Connection object:", connection);
    
    // Connect the nodes
    onConnect(connection);
    
    console.log("onConnect called - connection should be established");
    return true;
  } catch (error) {
    console.error("Error connecting nodes:", error);
    return false;
  }
}

/**
 * Helper function to create a properly formatted source handle
 */
function createSourceHandle(nodeId: string, outputName: string): string {
  // Create handle object exactly matching the format from a working connection
  const handleData = {
    dataType: "TextInput",  // The node type
    id: nodeId,
    name: "text",           // Always "text", not "Message"
    output_types: ["Message"]  // The output type is "Message"
  };
  
  // Use the same encoding as Langflow - replace double quotes with œ
  return JSON.stringify(handleData).replace(/"/g, "œ");
}

/**
 * Helper function to create a properly formatted target handle
 */
function createTargetHandle(nodeId: string, inputName: string, nodeType: string = "OpenAIModel"): string {
  // Create handle object exactly matching the format from a working connection
  const handleData = {
    fieldName: "input_value",  // This is what the OpenAI node expects, not "input"
    id: nodeId,
    inputTypes: ["Message"],   // Must match the source output_types
    type: "str"                // The underlying type
  };
  
  // Use the same encoding as Langflow - replace double quotes with œ
  return JSON.stringify(handleData).replace(/"/g, "œ");
}

export default {
  addExistingNode,
  processExistingNodeCommand,
  connectExistingNodes
};
