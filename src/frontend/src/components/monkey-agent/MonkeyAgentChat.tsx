/**
 * Monkey Agent Chat Component
 *
 * A focused component that handles placing existing nodes on the canvas.
 * Currently supporting the "Add text input" command to place a Text Input node.
 */

import { Send } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import useFlowStore from "../../stores/flowStore";
import { Button } from "../ui/button";
import { Input } from "../ui/input";

// Import our cleaned-up node placement tool
import existingNodeTools from "./demo/existing-node-placement";

// Types for messages
type Message = {
  role: "user" | "assistant";
  content: string;
};

export default function MonkeyAgentChat() {
  // Flow store hooks for manipulating nodes
  const setNodes = useFlowStore((state) => state.setNodes);
  const nodes = useFlowStore((state) => state.nodes);
  const onConnect = useFlowStore((state) => state.onConnect);

  // Component state
  const [currentMessage, setCurrentMessage] = useState("");
  const [messages, setMessages] = useState<Message[]>([
    {
      role: "assistant" as const,
      content: "Hi! I'm a simple AI assistant. Try typing: add text input",
    },
  ]);
  const [loading, setLoading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Scroll to bottom when messages change
  useEffect(() => {
    if (messagesEndRef.current) {
      messagesEndRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [messages]);

  // Toggle chat visibility
  const [isOpen, setIsOpen] = useState(false);
  const toggleChat = () => {
    setIsOpen(!isOpen);
  };

  // Handle input change
  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setCurrentMessage(e.target.value);
  };

  // Handle sending a message
  const handleSendMessage = async () => {
    if (!currentMessage.trim() || loading) return;

    // Add user message to chat
    const userMessage = { role: "user" as const, content: currentMessage };
    setMessages((prevMessages) => [...prevMessages, userMessage]);
    setCurrentMessage("");
    setLoading(true);

    try {
      // Process the command using our focused tool
      const result = existingNodeTools.processExistingNodeCommand(
        currentMessage,
        nodes,
        setNodes,
        onConnect,
      );

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

  // Handle keyboard events (Enter to send)
  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  };

  return (
    <div className="fixed bottom-4 right-4 z-50">
      {/* Chat toggle button */}
      <button
        onClick={toggleChat}
        className="flex h-12 w-12 items-center justify-center rounded-full bg-primary shadow-lg transition-colors hover:bg-primary/90"
      >
        {isOpen ? (
          <svg
            xmlns="http://www.w3.org/2000/svg"
            className="h-6 w-6 text-white"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M6 18L18 6M6 6l12 12"
            />
          </svg>
        ) : (
          <svg
            xmlns="http://www.w3.org/2000/svg"
            className="h-6 w-6 text-white"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z"
            />
          </svg>
        )}
      </button>

      {/* Chat window */}
      {isOpen && (
        <div className="absolute bottom-16 right-0 flex w-80 flex-col rounded-lg border bg-background shadow-xl md:w-96">
          {/* Chat header */}
          <div className="flex items-center justify-between border-b p-4">
            <h3 className="font-medium text-foreground">Monkey Agent</h3>
            <button
              onClick={toggleChat}
              className="text-gray-500 hover:text-gray-700"
            >
              <svg
                xmlns="http://www.w3.org/2000/svg"
                className="h-5 w-5"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M6 18L18 6M6 6l12 12"
                />
              </svg>
            </button>
          </div>

          {/* Chat messages */}
          <div className="max-h-96 flex-1 space-y-4 overflow-y-auto p-4">
            {messages.map((message, index) => (
              <div
                key={index}
                className={`flex ${
                  message.role === "user" ? "justify-end" : "justify-start"
                }`}
              >
                <div
                  className={`max-w-[80%] rounded-lg p-3 ${
                    message.role === "user"
                      ? "bg-primary text-primary-foreground"
                      : "bg-secondary text-secondary-foreground"
                  }`}
                >
                  {message.content}
                </div>
              </div>
            ))}
            <div ref={messagesEndRef} />
          </div>

          {/* Chat input */}
          <div className="border-t p-2">
            <div className="flex space-x-2">
              <Input
                value={currentMessage}
                onChange={handleInputChange}
                onKeyDown={handleKeyDown}
                placeholder="Try typing: add text input"
                disabled={loading}
              />
              <Button
                size="icon"
                disabled={!currentMessage.trim() || loading}
                onClick={handleSendMessage}
              >
                {loading ? (
                  <div className="h-4 w-4 animate-spin rounded-full border-b-2 border-white" />
                ) : (
                  <Send className="h-4 w-4" />
                )}
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
