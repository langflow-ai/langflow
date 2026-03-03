import { useCallback, useRef, useState } from "react";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import type { AgentRead } from "@/controllers/API/queries/agents";
import { ModelSelector } from "@/components/core/assistantPanel/components/model-selector";
import type { AssistantModel } from "@/components/core/assistantPanel/assistant-panel.types";
import { cn } from "@/utils/utils";
import { useAgentChat } from "../hooks/use-agent-chat";
import type { AgentMessage, AgentModel } from "../types";

interface AgentChatPanelProps {
  agent: AgentRead;
  onEditAgent: (agent: AgentRead) => void;
}

export function AgentChatPanel({ agent, onEditAgent }: AgentChatPanelProps) {
  const [inputValue, setInputValue] = useState("");
  const [selectedModel, setSelectedModel] = useState<AgentModel | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const {
    messages,
    isProcessing,
    handleSend,
    handleStopGeneration,
    handleClearHistory,
  } = useAgentChat(agent.id);

  const handleModelChange = useCallback((model: AssistantModel) => {
    setSelectedModel({
      id: model.id,
      name: model.name,
      provider: model.provider,
      displayName: model.displayName,
    });
  }, []);

  const handleSubmit = useCallback(() => {
    const trimmed = inputValue.trim();
    if (!trimmed) return;
    setInputValue("");
    handleSend(trimmed, selectedModel);
  }, [inputValue, selectedModel, handleSend]);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        handleSubmit();
      }
    },
    [handleSubmit],
  );

  const toolCount = agent.tool_components.length;

  return (
    <div className="flex h-full flex-1 flex-col">
      {/* Header */}
      <div className="flex items-center justify-between border-b px-4 py-2">
        <div className="flex items-center gap-3">
          <ForwardedIconComponent
            name={agent.icon || "Bot"}
            className="h-5 w-5"
          />
          <div>
            <h3 className="text-sm font-semibold">{agent.name}</h3>
            <p className="text-xs text-muted-foreground">
              {toolCount} {toolCount === 1 ? "tool" : "tools"}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <ModelSelector
            selectedModel={
              selectedModel
                ? {
                    id: selectedModel.id,
                    name: selectedModel.name,
                    provider: selectedModel.provider,
                    displayName: selectedModel.displayName,
                  }
                : null
            }
            onModelChange={handleModelChange}
          />
          <Button
            variant="ghost"
            size="icon"
            className="h-7 w-7"
            onClick={handleClearHistory}
            title="New Session"
            data-testid="new-session-button"
          >
            <ForwardedIconComponent name="RefreshCw" className="h-3.5 w-3.5" />
          </Button>
          <Button
            variant="ghost"
            size="icon"
            className="h-7 w-7"
            onClick={() => onEditAgent(agent)}
            title="Edit Agent"
            data-testid="edit-agent-button"
          >
            <ForwardedIconComponent name="Settings" className="h-3.5 w-3.5" />
          </Button>
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-4 py-4">
        {messages.length === 0 && (
          <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
            Send a message to start chatting with {agent.name}
          </div>
        )}
        <div className="flex flex-col gap-4">
          {messages.map((msg) => (
            <MessageBubble key={msg.id} message={msg} />
          ))}
          <div ref={messagesEndRef} />
        </div>
      </div>

      {/* Input */}
      <div className="border-t px-4 py-3">
        <div className="flex items-end gap-2">
          <Textarea
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Type a message..."
            className="min-h-[40px] max-h-[120px] resize-none"
            disabled={isProcessing}
            data-testid="agent-chat-input"
          />
          {isProcessing ? (
            <Button
              variant="ghost"
              size="icon"
              className="h-10 w-10 shrink-0"
              onClick={handleStopGeneration}
              data-testid="stop-generation-button"
            >
              <ForwardedIconComponent name="Square" className="h-4 w-4" />
            </Button>
          ) : (
            <Button
              variant="default"
              size="icon"
              className="h-10 w-10 shrink-0"
              onClick={handleSubmit}
              disabled={!inputValue.trim()}
              data-testid="send-message-button"
            >
              <ForwardedIconComponent name="Send" className="h-4 w-4" />
            </Button>
          )}
        </div>
      </div>
    </div>
  );
}

function MessageBubble({ message }: { message: AgentMessage }) {
  const isUser = message.role === "user";

  return (
    <div
      className={cn(
        "flex max-w-[80%] flex-col gap-1 rounded-lg px-3 py-2",
        isUser
          ? "ml-auto bg-primary text-primary-foreground"
          : "mr-auto bg-muted",
      )}
    >
      <p className="whitespace-pre-wrap text-sm">{message.content}</p>
      {message.status === "streaming" && !message.content && (
        <span className="text-xs opacity-60">Thinking...</span>
      )}
      {message.status === "error" && message.error && (
        <p className="text-xs text-destructive">{message.error}</p>
      )}
    </div>
  );
}
