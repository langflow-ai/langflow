import { Send } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { api } from "../../../controllers/API/api";
import useAlertStore from "../../../stores/alertStore";
import useAuthStore from "../../../stores/authStore";
import useFlowStore from "../../../stores/flowStore";
import { Button } from "../button";
import { Input } from "../input";

// Simple message interface
interface Message {
  role: string;
  content: string;
}

/**
 * A simple AI chat component that can add nodes to the canvas
 * using Langflow's existing store APIs
 */
export function SimpleAIChat() {
  // Get flow store methods
  const setNodes = useFlowStore((state) => state.setNodes);
  const nodes = useFlowStore((state) => state.nodes);
  const setEdges = useFlowStore((state) => state.setEdges);
  const edges = useFlowStore((state) => state.edges);
  const onConnect = useFlowStore((state) => state.onConnect);

  // Auth and alerts
  const setErrorData = useAlertStore((state) => state.setErrorData);
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated);

  // Component state
  const [apiKeyDialogOpen, setApiKeyDialogOpen] = useState(false);
  const [apiKey, setApiKey] = useState("");
  const [message, setMessage] = useState("");
  const [messages, setMessages] = useState<Message[]>([
    {
      role: "assistant",
      content:
        "Hi! I'm a simple AI assistant. Try asking me to add a node to your canvas.",
    },
  ]);
  const [loading, setLoading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Scroll to bottom when messages change
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // Handle sending API key
  const handleApiKeySave = async () => {
    if (!apiKey) return;

    setLoading(true);
    try {
      const response = await api.post("/api/v1/ai-agent/api-key", {
        api_key: apiKey,
      });

      if (response.status === 200) {
        setMessages((prevMessages) => [
          ...prevMessages,
          {
            role: "assistant",
            content:
              "API key saved successfully! I'm ready to help you build your workflow.",
          },
        ]);
        setApiKey("");
        setApiKeyDialogOpen(false);
      }
    } catch (error) {
      console.error("Error saving API key:", error);
      setErrorData({
        title: "Error saving API key",
        list: ["There was an error saving your API key. Please try again."],
      });
    } finally {
      setLoading(false);
    }
  };

  // Generate a unique node ID
  const generateNodeId = (nodeType: string): string => {
    // Create a simple ID based on type and timestamp
    return `${nodeType}_${Date.now()}`;
  };

  // Add a single node to the canvas
  const addNode = (nodeType: string, position = { x: 200, y: 200 }) => {
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
            description: "Added by AI Assistant",
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
      setErrorData({
        title: "Error adding node",
        list: ["There was an error adding the node to the canvas."],
      });
      return null;
    }
  };

  // Get template for specific node types
  const getNodeTemplate = (nodeType: string) => {
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

  // Connect two nodes
  const connectNodes = (sourceId: string, targetId: string) => {
    try {
      // Create connection config with proper handles
      const connection = {
        source: sourceId,
        target: targetId,
        sourceHandle: "output", // Required for connections to work
        targetHandle: "input", // Required for connections to work
      };

      // Use the store's connect function
      onConnect(connection);

      return true;
    } catch (error) {
      console.error("Error connecting nodes:", error);
      return false;
    }
  };

  // Find nodes by type
  const findNodesByType = (type: string) => {
    return nodes.filter((node) => node.data.type === type);
  };

  // Create a QA flow with connected nodes
  const createQAFlow = () => {
    try {
      // Create prompt node
      const promptId = addNode("PromptTemplate", { x: 200, y: 200 });

      // Create chat node below it
      const chatId = addNode("ChatOpenAI", { x: 200, y: 400 });

      if (promptId && chatId) {
        // Connect immediately - no timeout needed since we have proper handles now
        const connected = connectNodes(promptId, chatId);

        return { promptId, chatId, connected };
      }

      return null;
    } catch (error) {
      console.error("Error creating QA flow:", error);
      return null;
    }
  };

  // Process user message and handle commands
  const handleSendMessage = async () => {
    if (!message || loading) return;

    try {
      // Add user message to chat
      const userMessage = { role: "user", content: message };
      setMessages((prevMessages) => [...prevMessages, userMessage]);
      setMessage("");
      setLoading(true);

      // Process commands
      if (
        message.toLowerCase().includes("add chatgpt") ||
        message.toLowerCase().includes("add chat") ||
        message.toLowerCase().includes("add openai")
      ) {
        const nodeId = addNode("ChatOpenAI");

        if (nodeId) {
          setMessages((prevMessages) => [
            ...prevMessages,
            {
              role: "assistant",
              content: "I've added a ChatOpenAI node to your canvas.",
            },
          ]);
        }
      } else if (message.toLowerCase().includes("add prompt")) {
        const nodeId = addNode("PromptTemplate");

        if (nodeId) {
          setMessages((prevMessages) => [
            ...prevMessages,
            {
              role: "assistant",
              content: "I've added a PromptTemplate node to your canvas.",
            },
          ]);
        }
      } else if (
        message.toLowerCase().includes("connect prompt") ||
        message.toLowerCase().match(/connect.*to/i)
      ) {
        // Find nodes to connect
        const promptNodes = findNodesByType("PromptTemplate");
        const chatNodes = findNodesByType("ChatOpenAI");

        if (promptNodes.length === 0 || chatNodes.length === 0) {
          setMessages((prevMessages) => [
            ...prevMessages,
            {
              role: "assistant",
              content:
                "I need both a PromptTemplate and ChatOpenAI node on the canvas to connect them. Please add them first.",
            },
          ]);
        } else {
          // Get the most recently added nodes
          const sourceNode = promptNodes[promptNodes.length - 1];
          const targetNode = chatNodes[chatNodes.length - 1];

          // Connect the nodes directly
          if (connectNodes(sourceNode.id, targetNode.id)) {
            setMessages((prevMessages) => [
              ...prevMessages,
              {
                role: "assistant",
                content: `I've connected the PromptTemplate to the ChatOpenAI node.`,
              },
            ]);
          } else {
            setMessages((prevMessages) => [
              ...prevMessages,
              {
                role: "assistant",
                content:
                  "I tried to connect the nodes but encountered a technical issue. Please try again.",
              },
            ]);
          }
        }
      } else if (
        message.toLowerCase().includes("qa flow") ||
        message.toLowerCase().includes("create qa flow") ||
        message.toLowerCase().includes("build qa flow")
      ) {
        const flow = createQAFlow();

        if (flow) {
          setMessages((prevMessages) => [
            ...prevMessages,
            {
              role: "assistant",
              content:
                "I've created a simple QA flow with a PromptTemplate connected to a ChatOpenAI node.",
            },
          ]);
        }
      } else {
        // For other messages, respond with a placeholder
        setMessages((prevMessages) => [
          ...prevMessages,
          {
            role: "assistant",
            content:
              'I understand you want to: "' +
              message +
              '". This feature is coming soon! For now, try simple commands like "add ChatGPT" or "create QA flow".',
          },
        ]);
      }
    } catch (error: any) {
      console.error("Error sending message:", error);

      setMessages((prevMessages) => [
        ...prevMessages,
        {
          role: "assistant",
          content: `Sorry, I encountered an error: ${error.message || "Unknown error"}. Please try again.`,
        },
      ]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex h-full flex-col rounded-md border shadow-sm">
      {/* Chat header */}
      <div className="flex items-center justify-between border-b p-2">
        <div className="text-sm font-medium">Simple AI Assistant</div>
        <div className="flex gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => setApiKeyDialogOpen(true)}
          >
            Set API Key
          </Button>
        </div>
      </div>

      {/* API Key input */}
      {apiKeyDialogOpen && (
        <div className="border-b p-4">
          <div className="mb-2 text-sm">Enter your OpenAI API key:</div>
          <div className="flex space-x-2">
            <Input
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
              placeholder="sk-..."
              type="password"
            />
            <Button onClick={handleApiKeySave} disabled={!apiKey || loading}>
              Save
            </Button>
            <Button
              variant="outline"
              onClick={() => setApiKeyDialogOpen(false)}
            >
              Cancel
            </Button>
          </div>
        </div>
      )}

      {/* Chat messages */}
      <div className="flex-1 space-y-4 overflow-y-auto p-4">
        {messages.map((msg, index) => (
          <div
            key={index}
            className={`flex flex-col ${
              msg.role === "user" ? "items-end" : "items-start"
            }`}
          >
            <div
              className={`max-w-[80%] rounded-lg p-3 ${
                msg.role === "user"
                  ? "bg-primary text-primary-foreground"
                  : "bg-muted"
              }`}
            >
              {msg.content}
            </div>
          </div>
        ))}
        <div ref={messagesEndRef} />
      </div>

      {/* Input area */}
      <div className="border-t p-2">
        <div className="flex space-x-2">
          <Input
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            placeholder="Try typing: add ChatGPT"
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                handleSendMessage();
              }
            }}
            disabled={!isAuthenticated || loading}
          />
          <Button
            size="icon"
            disabled={!message || loading || !isAuthenticated}
            onClick={handleSendMessage}
          >
            {loading ? (
              <div className="h-4 w-4 animate-spin rounded-full border-b-2 border-primary" />
            ) : (
              <Send className="h-4 w-4" />
            )}
          </Button>
        </div>
        {!isAuthenticated && (
          <div className="mt-1 text-xs text-muted-foreground">
            Please sign in to use the AI assistant.
          </div>
        )}
      </div>
    </div>
  );
}

export default SimpleAIChat;
