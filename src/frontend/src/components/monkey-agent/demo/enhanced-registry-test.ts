/**
 * Enhanced Registry Test for the Monkey Agent
 *
 * This file tests the new approach of using an enhanced node registry
 * to better understand node types, inputs, outputs, and connection formats.
 */

import { produce } from "immer";
import flowStore from "../../../stores/flowStore";
import { useTypesStore } from "../../../stores/typesStore";
import {
  scapeJSONParse,
  scapeJSONStringify,
} from "../../../utils/reactflowUtils";

export interface CommandConfig {
  name: string;
  description: string;
  examples: string[];
  parameters: any[];
  execute: (message: string, params: any) => Promise<CommandResponse>;
}

export interface CommandResponse {
  success: boolean;
  message: string;
  action: string;
  details?: any;
}

/**
 * Finds a node template by description or template name
 * Prioritizes exact matches and follows specific node type preferences
 */
function findNodeTemplate(typeDescription: string) {
  const typesStore = useTypesStore.getState();
  const allTemplates = typesStore.templates;

  console.log(`Searching for node template: ${typeDescription}`);

  // First try: Exact type match
  if (allTemplates[typeDescription]) {
    console.log(`Found exact template match for ${typeDescription}`);
    return allTemplates[typeDescription];
  }

  // Second try: Search by description (prioritize matches)
  const templateArray = Object.values(allTemplates);

  // Common node type mapping (for easier reference)
  const nodeTypeMapping: { [key: string]: string[] } = {
    "document loader": ["DocumentLoader", "WebBaseLoader", "PDFLoader"],
    "openai embeddings": ["OpenAIEmbeddings"],
    "text splitter": [
      "RecursiveCharacterTextSplitter",
      "CharacterTextSplitter",
    ],
    "vector store": ["Chroma", "FAISS"],
    "text input": ["TextInput", "Input"],
    llm: ["OpenAI", "ChatOpenAI"],
    prompt: ["PromptTemplate", "ChatPromptTemplate"],
  };

  // Check if we have a common mapping
  const lowerTypeDesc = typeDescription.toLowerCase();
  for (const [key, values] of Object.entries(nodeTypeMapping)) {
    if (lowerTypeDesc.includes(key)) {
      // Try each of these node types
      for (const nodeType of values) {
        if (allTemplates[nodeType]) {
          console.log(
            `Found mapped template for "${lowerTypeDesc}": ${nodeType}`,
          );
          return allTemplates[nodeType];
        }
      }
    }
  }

  // Third try: Search for any node that includes the description in its display name
  const matchingTemplates = templateArray.filter((template) =>
    template.display_name?.toLowerCase().includes(lowerTypeDesc),
  );

  if (matchingTemplates.length > 0) {
    console.log(
      `Found ${matchingTemplates.length} templates matching description: ${typeDescription}`,
    );
    // Return the first match
    return matchingTemplates[0];
  }

  console.log(`No template found for ${typeDescription}`);
  return null;
}

/**
 * Adds a node to the canvas based on template type
 * Returns the node ID if successful, null otherwise
 */
function addNodeToCanvas(nodeType: string, position: { x: number; y: number }) {
  const typesStore = useTypesStore.getState();
  const flowStore = flowStore.getState();

  console.log(`Adding node: ${nodeType}`);

  // Find the node template
  const template = findNodeTemplate(nodeType);
  if (!template) {
    console.error(`No template found for ${nodeType}`);
    return null;
  }

  console.log(`Found template for ${nodeType}:`, template.display_name);

  try {
    // Create a new node with the template
    const newNodeId = flowStore.addNode({
      nodeType: template.type || "",
      node: template,
      position,
    });

    console.log(`Added ${nodeType} node with ID: ${newNodeId}`);
    return newNodeId;
  } catch (err) {
    console.error(`Error adding ${nodeType} node:`, err);
    return null;
  }
}

/**
 * Creates a formatted source handle for a connection
 */
function createSourceHandle(
  nodeId: string,
  nodeType: string,
  fieldName: string,
  outputTypes: string[] = ["Document"],
) {
  return scapeJSONStringify({
    dataType: nodeType,
    id: nodeId,
    name: fieldName,
    output_types: outputTypes,
  });
}

/**
 * Creates a formatted target handle for a connection
 */
function createTargetHandle(
  nodeId: string,
  fieldName: string,
  inputTypes: string[] = ["Document"],
) {
  return scapeJSONStringify({
    fieldName: fieldName,
    id: nodeId,
    inputTypes: inputTypes,
    type: "str",
  });
}

/**
 * Connects two nodes using the enhanced registry knowledge
 */
function connectNodes(
  sourceNodeId: string,
  sourceNodeType: string,
  sourceField: string,
  sourceOutputTypes: string[],
  targetNodeId: string,
  targetField: string,
  targetInputTypes: string[],
) {
  const flowStore = flowStore.getState();

  // Log the connection attempt
  console.log(
    `Connecting ${sourceNodeId} (${sourceField}) → ${targetNodeId} (${targetField})`,
  );

  // Create the source and target handles
  const sourceHandle = createSourceHandle(
    sourceNodeId,
    sourceNodeType,
    sourceField,
    sourceOutputTypes,
  );
  const targetHandle = createTargetHandle(
    targetNodeId,
    targetField,
    targetInputTypes,
  );

  console.log("Source handle:", sourceHandle);
  console.log("Target handle:", targetHandle);

  // Create a connection object
  const connection = {
    source: sourceNodeId,
    sourceHandle: sourceHandle,
    target: targetNodeId,
    targetHandle: targetHandle,
  };

  try {
    // Add the connection
    flowStore.onConnect(connection);
    console.log("Connection created:", connection);
    return true;
  } catch (err) {
    console.error("Error creating connection:", err);
    return false;
  }
}

/**
 * Command to add document to embeddings flow using the enhanced registry
 */
export const documentToEmbeddingsCommand: CommandConfig = {
  name: "Create Document Embeddings Flow",
  description:
    "Add a document loader and OpenAI Embeddings nodes, then connect them properly",
  examples: ["create document embeddings flow", "add document to embeddings"],
  parameters: [],

  execute: async (message: string, params: any) => {
    console.log("Starting document to embeddings flow creation");

    // 1. Add Document Loader node
    const documentPosition = { x: 100, y: 200 };
    const documentLoaderId = addNodeToCanvas(
      "DocumentLoader",
      documentPosition,
    );

    if (!documentLoaderId) {
      return {
        success: false,
        message:
          "I couldn't add the Document Loader node. Please make sure the template is available.",
        action: "error",
        details: { error: "Failed to add Document Loader" },
      };
    }

    // 2. Add OpenAI Embeddings node
    const embeddingsPosition = { x: 500, y: 200 };
    const embeddingsId = addNodeToCanvas(
      "OpenAIEmbeddings",
      embeddingsPosition,
    );

    if (!embeddingsId) {
      return {
        success: false,
        message:
          "I couldn't add the OpenAI Embeddings node. Please make sure the template is available.",
        action: "error",
        details: { error: "Failed to add OpenAI Embeddings" },
      };
    }

    // Wait a bit for the nodes to be properly initialized in the state
    await new Promise((resolve) => setTimeout(resolve, 500));

    // 3. Connect the nodes
    const connected = connectNodes(
      documentLoaderId,
      "DocumentLoader",
      "documents",
      ["Document", "List[Document]"],
      embeddingsId,
      "text",
      ["str", "Document", "List[Document]"],
    );

    if (!connected) {
      return {
        success: false,
        message:
          "I added both nodes but couldn't connect them. You may need to connect them manually.",
        action: "nodes_added_without_connection",
        details: {
          documentLoaderId,
          embeddingsId,
        },
      };
    }

    return {
      success: true,
      message:
        "I've created a document embeddings flow by adding a Document Loader and connecting it to an OpenAI Embeddings node.",
      action: "created_flow",
      details: {
        documentLoaderId,
        embeddingsId,
        connection: {
          source: documentLoaderId,
          target: embeddingsId,
          sourceField: "documents",
          targetField: "text",
        },
      },
    };
  },
};

/**
 * Command to create a text-to-LLM flow
 */
export const textToLLMCommand: CommandConfig = {
  name: "Create Text to LLM Flow",
  description: "Add a Text Input and OpenAI node, then connect them properly",
  examples: ["create text to llm flow", "add text input to openai"],
  parameters: [],

  execute: async (message: string, params: any) => {
    console.log("Starting text to LLM flow creation");

    // 1. Add Text Input node
    const textInputPosition = { x: 100, y: 200 };
    const textInputId = addNodeToCanvas("TextInput", textInputPosition);

    if (!textInputId) {
      return {
        success: false,
        message:
          "I couldn't add the Text Input node. Please make sure the template is available.",
        action: "error",
        details: { error: "Failed to add Text Input" },
      };
    }

    // 2. Add OpenAI node
    const openaiPosition = { x: 500, y: 200 };
    const openaiId = addNodeToCanvas("OpenAI", openaiPosition);

    if (!openaiId) {
      return {
        success: false,
        message:
          "I couldn't add the OpenAI node. Please make sure the template is available.",
        action: "error",
        details: { error: "Failed to add OpenAI" },
      };
    }

    // Wait a bit for the nodes to be properly initialized in the state
    await new Promise((resolve) => setTimeout(resolve, 500));

    // 3. Connect the nodes
    const connected = connectNodes(
      textInputId,
      "TextInput",
      "text",
      ["str", "Message"],
      openaiId,
      "input_value",
      ["str", "Message"],
    );

    if (!connected) {
      return {
        success: false,
        message:
          "I added both nodes but couldn't connect them. You may need to connect them manually.",
        action: "nodes_added_without_connection",
        details: {
          textInputId,
          openaiId,
        },
      };
    }

    return {
      success: true,
      message:
        "I've created a text-to-LLM flow by adding a Text Input and connecting it to an OpenAI node.",
      action: "created_flow",
      details: {
        textInputId,
        openaiId,
        connection: {
          source: textInputId,
          target: openaiId,
          sourceField: "text",
          targetField: "input_value",
        },
      },
    };
  },
};

// Export the available commands
export const enhancedRegistryCommands: CommandConfig[] = [
  documentToEmbeddingsCommand,
  textToLLMCommand,
];

// Function to handle commands
export async function handleEnhancedRegistryCommand(
  message: string,
): Promise<CommandResponse> {
  // Process the message to determine which command to execute
  const lowerMessage = message.toLowerCase();

  // Document to Embeddings flow
  if (
    lowerMessage.includes("document") &&
    (lowerMessage.includes("embeddings") || lowerMessage.includes("embedding"))
  ) {
    return documentToEmbeddingsCommand.execute(message, {});
  }

  // Text to LLM flow
  if (
    (lowerMessage.includes("text") || lowerMessage.includes("input")) &&
    (lowerMessage.includes("llm") || lowerMessage.includes("openai"))
  ) {
    return textToLLMCommand.execute(message, {});
  }

  // Default response if no command matches
  return {
    success: false,
    message:
      "I'm not sure what kind of flow you want to create. You can ask for a 'document embeddings flow' or a 'text to LLM flow'.",
    action: "command_not_recognized",
  };
}
