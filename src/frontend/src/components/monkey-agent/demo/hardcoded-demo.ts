/**
 * Hardcoded Demo Functions for the Monkey Agent
 *
 * This file contains the extracted functionality from the original SimpleAIChat component.
 * It's used as a reference for how nodes and connections were originally implemented
 * before moving to the more modular approach.
 */

import { AllNodeType, EdgeType } from "../../../types/flow";

/**
 * Generate a unique node ID based on type and timestamp
 */
export const generateNodeId = (nodeType: string): string => {
  return `${nodeType}_${Date.now()}`;
};

/**
 * Get template for specific node types
 */
export const getNodeTemplate = (nodeType: string) => {
  if (nodeType === "ChatOpenAI") {
    return {
      model_name: {
        value: "gpt-3.5-turbo",
        type: "str",
        required: true,
        list: false,
        show: true,
        readonly: false,
      },
    };
  } else if (nodeType === "PromptTemplate") {
    return {
      template: {
        value:
          "You are a helpful assistant that answers questions concisely.\n\nQuestion: {question}\n\nAnswer:",
        type: "str",
        required: true,
        list: false,
        show: true,
        readonly: false,
      },
    };
  }

  // Default empty template
  return {};
};

/**
 * Add a single node to the canvas
 */
export const addNode = (
  nodeType: string,
  position = { x: 200, y: 200 },
  setNodes: (updater: (oldNodes: AllNodeType[]) => AllNodeType[]) => void,
) => {
  try {
    // Generate ID for the new node
    const nodeId = generateNodeId(nodeType);

    // Create the node data
    const nodeData = {
      id: nodeId,
      type: "genericNode",
      position,
      data: {
        type: nodeType,
        id: nodeId,
        node: {
          template: getNodeTemplate(nodeType),
          description: "Added by Monkey Agent",
          display_name: nodeType,
          base_classes: [],
          documentation: "",
          tool_mode: false,
          frozen: false,
        },
      },
      width: 200,
      height: 400,
      selected: false,
      dragging: false,
    };

    // Add node to canvas (using 'as any' to bypass type checking)
    setNodes((oldNodes) => [...oldNodes, nodeData as any]);

    return nodeId;
  } catch (error) {
    console.error("Error adding node:", error);
    return null;
  }
};

/**
 * Connect two nodes
 */
export const connectNodes = (
  sourceId: string,
  targetId: string,
  onConnect: (connection: any) => void,
) => {
  try {
    // Create connection config with proper handles
    const connection = {
      source: sourceId,
      target: targetId,
      sourceHandle: "output", // Required for connections to work
      targetHandle: "input", // Required for connections to work
    };

    // Use the connect function from the flow store
    onConnect(connection);

    return true;
  } catch (error) {
    console.error("Error connecting nodes:", error);
    return false;
  }
};

/**
 * Find nodes by type
 */
export const findNodesByType = (nodes: AllNodeType[], type: string) => {
  return nodes.filter((node) => node.data.type === type);
};

/**
 * Create a QA flow with connected nodes
 */
export const createQAFlow = (
  setNodes: (updater: (oldNodes: AllNodeType[]) => AllNodeType[]) => void,
  onConnect: (connection: any) => void,
) => {
  try {
    // Create prompt node
    const promptId = addNode("PromptTemplate", { x: 200, y: 200 }, setNodes);

    // Create chat node below it
    const chatId = addNode("ChatOpenAI", { x: 200, y: 400 }, setNodes);

    if (promptId && chatId) {
      // Connect the nodes
      const connected = connectNodes(promptId, chatId, onConnect);

      return { promptId, chatId, connected };
    }

    return null;
  } catch (error) {
    console.error("Error creating QA flow:", error);
    return null;
  }
};

/**
 * Command handler for processing user messages
 */
export const processCommand = (
  message: string,
  nodes: AllNodeType[],
  setNodes: (updater: (oldNodes: AllNodeType[]) => AllNodeType[]) => void,
  onConnect: (connection: any) => void,
) => {
  // Check for chat/LLM commands
  if (
    message.toLowerCase().includes("add chatgpt") ||
    message.toLowerCase().includes("add chat") ||
    message.toLowerCase().includes("add openai")
  ) {
    const nodeId = addNode("ChatOpenAI", { x: 200, y: 200 }, setNodes);

    if (nodeId) {
      return {
        success: true,
        message: "I've added a ChatOpenAI node to your canvas.",
        action: "added_node",
        details: { nodeType: "ChatOpenAI", nodeId },
      };
    }
  }
  // Check for prompt commands
  else if (message.toLowerCase().includes("add prompt")) {
    const nodeId = addNode("PromptTemplate", { x: 200, y: 200 }, setNodes);

    if (nodeId) {
      return {
        success: true,
        message: "I've added a PromptTemplate node to your canvas.",
        action: "added_node",
        details: { nodeType: "PromptTemplate", nodeId },
      };
    }
  }
  // Check for connection commands
  else if (
    message.toLowerCase().includes("connect prompt") ||
    message.toLowerCase().match(/connect.*to/i)
  ) {
    // Find nodes to connect
    const promptNodes = findNodesByType(nodes, "PromptTemplate");
    const chatNodes = findNodesByType(nodes, "ChatOpenAI");

    if (promptNodes.length === 0 || chatNodes.length === 0) {
      return {
        success: false,
        message:
          "I need both a PromptTemplate and ChatOpenAI node on the canvas to connect them. Please add them first.",
        action: "connection_failed",
        details: { reason: "missing_nodes" },
      };
    } else {
      // Get the most recently added nodes
      const sourceNode = promptNodes[promptNodes.length - 1];
      const targetNode = chatNodes[chatNodes.length - 1];

      // Connect the nodes
      if (connectNodes(sourceNode.id, targetNode.id, onConnect)) {
        return {
          success: true,
          message: "I've connected the PromptTemplate to the ChatOpenAI node.",
          action: "connected_nodes",
          details: { sourceId: sourceNode.id, targetId: targetNode.id },
        };
      } else {
        return {
          success: false,
          message:
            "I tried to connect the nodes but encountered a technical issue. Please try again.",
          action: "connection_failed",
          details: { reason: "technical_error" },
        };
      }
    }
  }
  // Check for flow creation commands
  else if (
    message.toLowerCase().includes("qa flow") ||
    message.toLowerCase().includes("create qa flow") ||
    message.toLowerCase().includes("build qa flow")
  ) {
    const flow = createQAFlow(setNodes, onConnect);

    if (flow) {
      return {
        success: true,
        message:
          "I've created a simple QA flow with a PromptTemplate connected to a ChatOpenAI node.",
        action: "created_flow",
        details: {
          flowType: "qa",
          nodes: [flow.promptId, flow.chatId],
          connected: flow.connected,
        },
      };
    } else {
      return {
        success: false,
        message: "I couldn't create the QA flow. Please try again.",
        action: "flow_creation_failed",
        details: { reason: "technical_error" },
      };
    }
  }

  // Default response for unrecognized commands
  return {
    success: false,
    message: `I understand you want to: "${message}". This feature is coming soon! For now, try simple commands like "add ChatGPT" or "create QA flow".`,
    action: "unrecognized_command",
    details: { userMessage: message },
  };
};

export default {
  generateNodeId,
  getNodeTemplate,
  addNode,
  connectNodes,
  findNodesByType,
  createQAFlow,
  processCommand,
};
