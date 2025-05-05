import useFlowStore from "../../../../stores/flowStore";
import { AllNodeType, EdgeType } from "../../../../types/flow";

// Define Tool interface
export interface AIAssistantTool {
  name: string;
  description: string;
  execute: (...args: any[]) => Promise<string> | string;
}

// Get the type of the flow store
type FlowStore = ReturnType<typeof useFlowStore>;

// Create a base class for node creation
export class NodeCreationTool implements AIAssistantTool {
  name: string;
  description: string;
  nodeType: string;

  constructor(nodeType: string) {
    this.nodeType = nodeType;
    this.name = `add${nodeType}`;
    this.description = `Add a ${nodeType} node to the canvas.`;
  }

  execute(flowStore: { setNodes: FlowStore["setNodes"] }) {
    // Generate ID for the new node
    const nodeId = this.generateNodeId();

    // Create a basic node with properly typed template
    const nodeData = {
      id: nodeId,
      type: "genericNode",
      position: { x: 200, y: 200 },
      data: {
        type: this.nodeType,
        id: nodeId,
        node: {
          template: this.getNodeTemplate(),
          description: "Added by AI Assistant",
          display_name: this.nodeType,
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

    // Add node to canvas
    flowStore.setNodes((oldNodes) => [...oldNodes, nodeData as any]);

    return `Added a ${this.nodeType} node to the canvas.`;
  }

  generateNodeId(): string {
    // Create a simple ID based on type and timestamp
    return `${this.nodeType}_${Date.now()}`;
  }

  private getNodeTemplate(): any {
    // Return template specific to the node type
    if (this.nodeType === "ChatOpenAI") {
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
    } else if (this.nodeType === "PromptTemplate") {
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
  }
}

// Node connection tool
export class NodeConnectionTool implements AIAssistantTool {
  name: string = "connectNodes";
  description: string = "Connect two nodes on the canvas.";

  execute(flowStore: FlowStore, sourceId: string, targetId: string): string {
    try {
      // Create a valid connection between nodes
      const connection = {
        source: sourceId,
        target: targetId,
        sourceHandle: null,
        targetHandle: null,
      };

      // Use the onConnect function from the flow store to create the edge
      flowStore.onConnect(connection);

      return `Connected node ${sourceId} to node ${targetId}.`;
    } catch (error) {
      console.error("Error connecting nodes:", error);
      return `Failed to connect nodes: ${error instanceof Error ? error.message : String(error)}`;
    }
  }
}

// Flow creation tool
export class FlowCreationTool implements AIAssistantTool {
  name: string = "createQAFlow";
  description: string =
    "Create a QA flow with a PromptTemplate connected to a ChatOpenAI node.";

  execute(flowStore: FlowStore): string {
    try {
      // Create the prompt node
      const promptTool = new NodeCreationTool("PromptTemplate");
      const promptId = promptTool.generateNodeId();

      // Create the chat node
      const chatTool = new NodeCreationTool("ChatOpenAI");
      const chatId = chatTool.generateNodeId();

      // Add both nodes
      const promptNode = {
        id: promptId,
        type: "genericNode",
        position: { x: 200, y: 200 },
        data: {
          type: "PromptTemplate",
          id: promptId,
          node: {
            template: {
              template: {
                value:
                  "You are a helpful assistant that answers questions concisely.\n\nQuestion: {question}\n\nAnswer:",
                type: "str",
                required: true,
                list: false,
                show: true,
                readonly: false,
              },
            },
            description: "Added by AI Assistant",
            display_name: "PromptTemplate",
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

      const chatNode = {
        id: chatId,
        type: "genericNode",
        position: { x: 200, y: 400 },
        data: {
          type: "ChatOpenAI",
          id: chatId,
          node: {
            template: {
              model_name: {
                value: "gpt-3.5-turbo",
                type: "str",
                required: true,
                list: false,
                show: true,
                readonly: false,
              },
            },
            description: "Added by AI Assistant",
            display_name: "ChatOpenAI",
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

      // Add nodes to canvas
      flowStore.setNodes((oldNodes) => [
        ...oldNodes,
        promptNode as any,
        chatNode as any,
      ]);

      // Wait a moment for nodes to be added before connecting
      setTimeout(() => {
        // Create a valid connection between nodes
        const connection = {
          source: promptId,
          target: chatId,
          sourceHandle: null,
          targetHandle: null,
        };

        // Use the onConnect function from the flow store to create the edge
        flowStore.onConnect(connection);
      }, 100);

      return "Created a QA flow with a PromptTemplate connected to a ChatOpenAI node.";
    } catch (error) {
      console.error("Error creating QA flow:", error);
      return `Failed to create QA flow: ${error instanceof Error ? error.message : String(error)}`;
    }
  }
}

// Create and export the tools
export const createToolbox = (flowStore: FlowStore) => {
  return {
    addChatOpenAI: new NodeCreationTool("ChatOpenAI"),
    addPromptTemplate: new NodeCreationTool("PromptTemplate"),
    connectNodes: new NodeConnectionTool(),
    createQAFlow: new FlowCreationTool(),
  };
};

export type AIAssistantToolbox = ReturnType<typeof createToolbox>;
