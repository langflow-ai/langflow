import { useState } from "react";
import { v4 as uuid } from "uuid";
import { api } from "@/controllers/API/api";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import LoadingIcon from "@/components/ui/loading";
import { getURL } from "@/controllers/API/helpers/constants";

interface PlaygroundTabProps {
  publishedFlowData: any;
}

interface Message {
  id: string;
  type: "user" | "ai";
  text: string;
  timestamp: Date;
}

export default function PlaygroundTab({ publishedFlowData }: PlaygroundTabProps) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sessionId] = useState(() => uuid());

  const sendMessage = async () => {
    if (!input.trim() || isLoading) return;

    const userMessage: Message = {
      id: uuid(),
      type: "user",
      text: input.trim(),
      timestamp: new Date(),
    };

    setMessages((prev) => [...prev, userMessage]);
    setInput("");
    setIsLoading(true);
    setError(null);

    try {
      const response = await api.post(
        `${getURL("RUN")}/${publishedFlowData.flow_id}?stream=false`,
        {
          input_value: input.trim(),
          session_id: sessionId,
        }
      );

          // const response = await api.post(`/api/v1/spec/convert`, {
          //   spec_yaml: payload.spec_yaml,
          //   variables: payload.variables || null,
          //   tweaks: payload.tweaks || null,
          // });

      // Extract AI response text from various possible response formats
      let aiText: string;

      if (response.data?.outputs?.[0]?.outputs?.[0]?.message?.text) {
        aiText = response.data.outputs[0].outputs[0].message.text;
      } else if (response.data?.outputs?.[0]?.results?.message?.text) {
        aiText = response.data.outputs[0].results.message.text;
      } else if (response.data?.outputs?.[0]?.outputs?.[0]?.results?.message?.text) {
        aiText = response.data.outputs[0].outputs[0].results.message.text;
      } else if (typeof response.data === "string") {
        aiText = response.data;
      } else {
        // Fallback: stringify the response
        aiText = JSON.stringify(response.data, null, 2);
      }

      const aiMessage: Message = {
        id: uuid(),
        type: "ai",
        text: aiText,
        timestamp: new Date(),
      };

      setMessages((prev) => [...prev, aiMessage]);
    } catch (err: any) {
      console.error("Error running flow:", err);
      const errorMessage = err.response?.data?.detail || err.message || "Failed to get response";
      setError(errorMessage);

      const errorAiMessage: Message = {
        id: uuid(),
        type: "ai",
        text: `Error: ${errorMessage}`,
        timestamp: new Date(),
      };

      setMessages((prev) => [...prev, errorAiMessage]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleKeyPress = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  return (
    <div className="flex h-full w-full flex-col bg-background">
      {/* Messages Area */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.length === 0 && (
          <div className="flex h-full items-center justify-center text-muted-foreground">
            <div className="text-center">
              <p className="text-lg font-medium">Start a conversation</p>
              <p className="text-sm mt-2">Send a message to test this flow</p>
            </div>
          </div>
        )}

        {messages.map((message) => (
          <div
            key={message.id}
            className={`flex ${message.type === "user" ? "justify-end" : "justify-start"}`}
          >
            <div
              className={`max-w-[80%] rounded-lg px-4 py-2 ${
                message.type === "user"
                  ? "bg-primary text-primary-foreground"
                  : "bg-muted text-foreground"
              }`}
            >
              <div className="whitespace-pre-wrap break-words">{message.text}</div>
              <div className="text-xs opacity-70 mt-1">
                {message.timestamp.toLocaleTimeString()}
              </div>
            </div>
          </div>
        ))}

        {isLoading && (
          <div className="flex justify-start">
            <div className="bg-muted rounded-lg px-4 py-2">
              <LoadingIcon />
            </div>
          </div>
        )}
      </div>

      {/* Input Area */}
      <div className="border-t border-border p-4">
        {error && (
          <div className="mb-2 text-sm text-destructive">
            {error}
          </div>
        )}

        <div className="flex gap-2">
          <Textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyPress}
            placeholder="Type your message... (Enter to send, Shift+Enter for new line)"
            className="flex-1 min-h-[60px] max-h-[120px] resize-none"
            disabled={isLoading}
          />
          <Button
            onClick={sendMessage}
            disabled={!input.trim() || isLoading}
            className="self-end"
          >
            {isLoading ? <LoadingIcon /> : "Send"}
          </Button>
        </div>
      </div>
    </div>
  );
}
