import { useState, useRef, useEffect } from "react";
import { useReactFlow, useStoreApi } from "reactflow";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "../../ui/dialog";
import { Input } from "../input";
import { Button } from "../button";
import { Send } from "lucide-react";
import { AIMessage } from "./message";
import { api } from "../../../controllers/API/api";
import useAlertStore from "../../../stores/alertStore";
import useAuthStore from "../../../stores/authStore";
import useFlowsManagerStore from "../../../stores/flowsManagerStore";

// Define APIKeyDialogProps interface
interface APIKeyDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onApiKeySave: (key: string) => void;
}

// APIKeyDialog component for setting the OpenAI API key
const APIKeyDialog: React.FC<APIKeyDialogProps> = ({ open, onOpenChange, onApiKeySave }) => {
  const [apiKey, setApiKey] = useState("");
  const [saving, setSaving] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!apiKey) {
      return;
    }
    
    setSaving(true);
    try {
      await onApiKeySave(apiKey);
      onOpenChange(false);
    } catch (error) {
      console.error("Error saving API key:", error);
    } finally {
      setSaving(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Set OpenAI API Key</DialogTitle>
          <DialogDescription>
            Enter your OpenAI API key to enable the AI assistant.
            This key will be stored securely for your account.
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          <Input
            value={apiKey}
            onChange={(e) => setApiKey(e.target.value)}
            placeholder="sk-..."
            className="col-span-3"
          />
          <DialogFooter className="sm:justify-end">
            <Button 
              type="submit" 
              disabled={saving || !apiKey}
            >
              {saving ? "Saving..." : "Save"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
};

export interface AIAssistantProps {
  flow: any;
}

interface Message {
  role: string;
  content: string;
}

export function AIAgentChat({ flow }: AIAssistantProps) {
  // Skip rendering if flow is not available
  if (!flow) {
    return null;
  }

  const reactFlowInstance = useReactFlow();
  const store = useStoreApi();
  
  const setErrorData = useAlertStore((state) => state.setErrorData);
  const flows = useFlowsManagerStore((state) => state.flows);
  const setFlows = useFlowsManagerStore((state) => state.setFlows);
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated);
  
  const [apiKeyDialogOpen, setApiKeyDialogOpen] = useState(false);
  const [message, setMessage] = useState("");
  const [messages, setMessages] = useState<Message[]>([
    {
      role: "assistant",
      content: "Hi! I'm your AI assistant. I can help you build and modify your workflow. How can I help you today?",
    },
  ]);
  const [loading, setLoading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  // Handle sending API key to backend
  const handleApiKeySave = async (apiKey: string) => {
    try {
      const response = await api.post("/api/v1/ai-agent/api-key", {
        api_key: apiKey,
      });
      
      if (response.status === 200) {
        setMessages((prevMessages) => [
          ...prevMessages,
          {
            role: "assistant",
            content: "API key saved successfully! I'm ready to help you build your workflow.",
          },
        ]);
      }
    } catch (error) {
      console.error("Error saving API key:", error);
      setErrorData({
        title: "Error saving API key",
        list: ["There was an error saving your API key. Please try again."],
      });
    }
  };

  // Process user message and get AI response
  const handleSendMessage = async () => {
    if (!message || loading) return;

    try {
      // Add user message to chat
      const userMessage = { role: "user", content: message };
      setMessages((prevMessages) => [...prevMessages, userMessage]);
      setMessage("");
      setLoading(true);

      // Get current flow state
      const nodes = reactFlowInstance.getNodes();
      const edges = reactFlowInstance.getEdges();
      const flowState = {
        nodes: nodes,
        edges: edges,
      };

      // Send request to AI agent endpoint
      const response = await api.post("/api/v1/ai-agent/chat", {
        message: userMessage.content,
        flow_state: flowState,
      });

      // Handle AI response
      const aiResponse = response.data;
      
      // Add AI message to chat
      setMessages((prevMessages) => [
        ...prevMessages,
        { role: "assistant", content: aiResponse.message },
      ]);

      // Process actions if any
      if (aiResponse.actions && aiResponse.actions.length > 0) {
        handleAgentActions(aiResponse.actions);
      }
    } catch (error: any) {
      console.error("Error sending message:", error);
      
      // Handle API key errors
      if (error.response?.data?.detail?.includes("API key")) {
        setMessages((prevMessages) => [
          ...prevMessages,
          {
            role: "assistant",
            content: "I need an OpenAI API key to help you. Please click the 'Set API Key' button to provide your key.",
          },
        ]);
      } else {
        // Generic error message
        setMessages((prevMessages) => [
          ...prevMessages,
          {
            role: "assistant",
            content: `Sorry, I encountered an error: ${error.message || "Unknown error"}. Please try again.`,
          },
        ]);
      }
    } finally {
      setLoading(false);
    }
  };

  // Process AI agent actions
  const handleAgentActions = (actions: any[]) => {
    try {
      // Get current state
      const nodes = reactFlowInstance.getNodes();
      const edges = reactFlowInstance.getEdges();
      let modified = false;

      // Process each action
      actions.forEach((action) => {
        switch (action.type) {
          case "add_node":
            // Add node with correct position
            if (!action.data.position) {
              // Set default position if none provided
              action.data.position = { x: 100, y: 100 };
            }
            reactFlowInstance.addNodes(action.data);
            modified = true;
            break;

          case "edit_node":
            // Edit node parameters
            const nodeToEdit = nodes.find((n) => n.id === action.node_id);
            if (nodeToEdit) {
              // Update node parameters
              const updatedNode = { ...nodeToEdit };
              const template = updatedNode.data.node.template || {};
              Object.entries(action.parameters).forEach(([key, value]) => {
                if (template[key]) {
                  template[key].value = value;
                } else {
                  // Create new parameter if it doesn't exist
                  template[key] = { value: value, type: typeof value };
                }
              });
              reactFlowInstance.setNodes((nds) => 
                nds.map((n) => (n.id === action.node_id ? updatedNode : n))
              );
              modified = true;
            }
            break;

          case "connect_nodes":
            // Connect nodes
            const newEdge = {
              id: `${action.source_id}-${action.target_id}`,
              source: action.source_id,
              target: action.target_id,
              sourceHandle: action.source_handle,
              targetHandle: action.target_handle,
            };
            reactFlowInstance.addEdges(newEdge);
            modified = true;
            break;

          case "create_workflow":
            // For now, just display a message
            setMessages((prevMessages) => [
              ...prevMessages,
              {
                role: "assistant",
                content: `I'll create a new workflow named "${action.name}" for you. This functionality is still in development.`,
              },
            ]);
            break;

          default:
            console.warn(`Unknown action type: ${action.type}`);
        }
      });

      // Update flow if modified
      if (modified && flow.id) {
        // Get the updated flow data with latest nodes and edges
        const updatedNodes = reactFlowInstance.getNodes();
        const updatedEdges = reactFlowInstance.getEdges();
        
        const updatedFlow = {
          ...flow,
          data: JSON.stringify({ nodes: updatedNodes, edges: updatedEdges }),
        };
        
        // Update flows in store
        const updatedFlows = flows?.map(f => 
          f.id === flow.id ? updatedFlow : f
        ) || [];
        
        setFlows(updatedFlows);
      }
    } catch (error) {
      console.error("Error handling agent actions:", error);
      setErrorData({
        title: "Error applying changes",
        list: ["There was an error applying the requested changes to your workflow."],
      });
    }
  };

  return (
    <div className="flex flex-col h-full">
      {/* API Key Dialog */}
      <APIKeyDialog
        open={apiKeyDialogOpen}
        onOpenChange={setApiKeyDialogOpen}
        onApiKeySave={handleApiKeySave}
      />
      
      {/* Chat header */}
      <div className="flex justify-between items-center p-2 border-b">
        <div className="text-sm font-medium">AI Assistant</div>
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
      
      {/* Chat messages */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.map((msg, index) => (
          <AIMessage key={index} message={msg} />
        ))}
        <div ref={messagesEndRef} />
      </div>
      
      {/* Input area */}
      <div className="border-t p-2">
        <div className="flex space-x-2">
          <Input
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            placeholder="Ask the AI assistant..."
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
          <div className="text-xs text-muted-foreground mt-1">
            Please sign in to use the AI assistant.
          </div>
        )}
      </div>
    </div>
  );
}

// Export a default component for use in other files
export default AIAgentChat;
