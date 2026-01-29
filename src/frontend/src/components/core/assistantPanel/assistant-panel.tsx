import { useMemo, useState } from "react";
import { useGetEnabledModels } from "@/controllers/API/queries/models/use-get-enabled-models";
import { useGetModelProviders } from "@/controllers/API/queries/models/use-get-model-providers";
import { cn } from "@/utils/utils";
import type { AssistantMessage, AssistantModel, AssistantPanelProps } from "./assistant-panel.types";
import { AssistantEmptyState } from "./components/assistant-empty-state";
import { AssistantHeader } from "./components/assistant-header";
import { AssistantInput } from "./components/assistant-input";
import { AssistantMessageItem } from "./components/assistant-message";
import { AssistantNoModelsState } from "./components/assistant-no-models-state";

export function AssistantPanel({ isOpen, onClose }: AssistantPanelProps) {
  const [messages, setMessages] = useState<AssistantMessage[]>([]);
  const { data: providersData = [] } = useGetModelProviders({});
  const { data: enabledModelsData } = useGetEnabledModels();

  // Check if there are any enabled models available
  const hasEnabledModels = useMemo(() => {
    const enabledModels = enabledModelsData?.enabled_models || {};

    return providersData.some((provider) => {
      if (!provider.is_enabled) return false;
      const providerEnabledModels = enabledModels[provider.provider] || {};
      return provider.models.some(
        (model) =>
          providerEnabledModels[model.model_name] === true &&
          !model.model_name.includes("embedding"),
      );
    });
  }, [providersData, enabledModelsData]);

  const handleSend = (content: string, _model: AssistantModel | null) => {
    const userMessage: AssistantMessage = {
      id: crypto.randomUUID(),
      role: "user",
      content,
      timestamp: new Date(),
    };
    setMessages((prev) => [...prev, userMessage]);
  };

  const handleSuggestionClick = (suggestion: string) => {
    handleSend(suggestion, null);
  };

  const handleClearHistory = () => {
    setMessages([]);
  };

  const hasMessages = messages.length > 0;

  return (
    <div
      className={cn(
        "fixed left-0 top-12 z-50 flex h-[calc(100%-48px)] w-[500px] flex-col shadow-xl transition-transform duration-300",
        isOpen ? "translate-x-0" : "-translate-x-full",
      )}
    >
      {/* Background */}
      <div className="absolute inset-0 overflow-hidden bg-background">
        {/* Gradient glow at bottom */}
        <div
          className="absolute -left-6 bottom-0 h-[505px] w-[936px] blur-[48px]"
          style={{
            background: "linear-gradient(89deg, #19F0A5 0%, #BA75FF 50%, #0FE3FF 100%)",
            opacity: 0.18,
            transform: "rotate(89.1deg)",
          }}
        />
        {/* Noise overlay - very subtle */}
        <div
          className="absolute inset-0 opacity-[0.03]"
          style={{
            backgroundImage: `url("data:image/svg+xml,%3Csvg viewBox='0 0 512 512' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='noise'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.65' numOctaves='3' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23noise)'/%3E%3C/svg%3E")`,
          }}
        />
      </div>
      {/* Content */}
      <div className="relative z-10 flex h-full flex-col">
        <AssistantHeader onClose={onClose} onClearHistory={handleClearHistory} />
        <div className="flex flex-1 flex-col overflow-hidden">
          {!hasEnabledModels ? (
            <AssistantNoModelsState />
          ) : hasMessages ? (
            <div className="flex-1 overflow-y-auto px-4 py-6">
              {messages.map((msg) => (
                <AssistantMessageItem key={msg.id} message={msg} />
              ))}
            </div>
          ) : (
            <AssistantEmptyState onSuggestionClick={handleSuggestionClick} />
          )}
        </div>
        <AssistantInput
          onSend={handleSend}
          disabled={!hasEnabledModels}
          placeholder={!hasEnabledModels ? "Configure Model Providers..." : undefined}
        />
      </div>
    </div>
  );
}

export default AssistantPanel;
