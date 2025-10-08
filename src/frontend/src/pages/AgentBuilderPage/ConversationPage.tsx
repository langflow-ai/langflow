import { useEffect, useState } from "react";
import { useLocation } from "react-router-dom";
import Breadcrumb from "@/components/common/Breadcrumb";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { useAgentBuilderStream } from "@/hooks/useAgentBuilderStream";
import StreamingMessages from "@/components/AgentBuilder/StreamingMessages";
import { useCustomNavigate } from "@/customization/hooks/use-custom-navigate";

export default function ConversationPage() {
  const location = useLocation();
  const navigate = useCustomNavigate();
  const [promptValue, setPromptValue] = useState("");

  const { messages, isLoading, startStream } = useAgentBuilderStream();

  // Get initial prompt from navigation state
  const initialPrompt = location.state?.prompt;

  // Start streaming with initial prompt on mount
  useEffect(() => {
    if (initialPrompt) {
      startStream(initialPrompt);
    }
  }, [initialPrompt, startStream]);

  const handlePromptSubmit = () => {
    if (promptValue.trim()) {
      startStream(promptValue);
      setPromptValue("");
    }
  };

  // Breadcrumb navigation
  const breadcrumbItems = [
    { label: "Dashboard", href: "/" },
    { label: "Genesis Studio", href: "/studio-home", beta: true },
    { label: "AI Agent Builder", href: "/agent-builder" },
    { label: "Conversation" },
  ];

  return (
    <div className="flex h-full w-full flex-col">
      {/* Header with Breadcrumb */}
      <div className="border-b bg-background px-4 py-3 md:px-6">
        <div className="flex items-center justify-between">
          <Breadcrumb items={breadcrumbItems} />
          <button
            onClick={() => navigate("/agent-builder")}
            className="text-sm text-muted-foreground hover:text-foreground"
          >
            New Conversation
          </button>
        </div>
      </div>

      {/* Chat Messages Area */}
      <div className="flex-1 overflow-y-auto px-4 py-6">
        <div className="mx-auto max-w-4xl">
          <StreamingMessages messages={messages} isLoading={isLoading} />
        </div>
      </div>

      {/* Input Section - Fixed at bottom */}
      <div className="border-t bg-background px-4 py-4">
        <div className="mx-auto max-w-4xl">
          <div className="relative">
            <textarea
              value={promptValue}
              onChange={(e) => setPromptValue(e.target.value)}
              placeholder="Continue the conversation..."
              className="w-full min-h-[80px] p-3 pr-12 rounded-lg border border-input bg-background text-sm resize-none focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2"
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  handlePromptSubmit();
                }
              }}
            />
            <button
              onClick={handlePromptSubmit}
              className="absolute right-3 bottom-3 p-2 rounded-md bg-primary text-primary-foreground hover:bg-primary/90 disabled:opacity-50 disabled:cursor-not-allowed"
              disabled={!promptValue.trim() || isLoading}
              aria-label="Submit prompt"
            >
              <ForwardedIconComponent name="Send" className="h-4 w-4" />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
