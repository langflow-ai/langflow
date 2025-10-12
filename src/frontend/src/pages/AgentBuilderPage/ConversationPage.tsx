import { useEffect, useState } from "react";
import { useLocation } from "react-router-dom";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { useAgentBuilderStream } from "@/hooks/useAgentBuilderStream";
import StreamingMessages from "@/components/AgentBuilder/StreamingMessages";
import { useConvertSpec } from "@/controllers/API/queries/spec/use-convert-spec";
import { usePostAddFlow } from "@/controllers/API/queries/flows/use-post-add-flow";
import useAlertStore from "@/stores/alertStore";
import { useFolderStore } from "@/stores/foldersStore";
import FlowPanel from "./FlowPanel";

export default function ConversationPage() {
  const location = useLocation();
  const [promptValue, setPromptValue] = useState("");
  const [flowData, setFlowData] = useState<any>(null);
  const [createdFlowId, setCreatedFlowId] = useState<string | null>(null);
  const [yamlSpec, setYamlSpec] = useState<string>("");
  const [leftPanelWidth, setLeftPanelWidth] = useState(50); // Percentage
  const [isDragging, setIsDragging] = useState(false);

  const { messages, isLoading, startStream, reset } = useAgentBuilderStream();
  const convertSpecMutation = useConvertSpec();
  const createFlowMutation = usePostAddFlow();
  const setErrorData = useAlertStore((state) => state.setErrorData);
  const myCollectionId = useFolderStore((state) => state.myCollectionId);
  const folders = useFolderStore((state) => state.folders);

  // Get initial prompt from navigation state
  const initialPrompt = location.state?.prompt;

  // Reset conversation state on page load/reload
  useEffect(() => {
    reset();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Start streaming with initial prompt on mount
  useEffect(() => {
    if (initialPrompt) {
      startStream(initialPrompt);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [initialPrompt]);

  const handlePromptSubmit = () => {
    if (promptValue.trim()) {
      startStream(promptValue);
      setPromptValue("");
    }
  };

  const handleTriggerBuild = () => {
    // Send message to trigger Builder Agent to generate YAML
    startStream("build agent now");
  };

  // Handle resizable panel dragging
  const handleDragStart = () => {
    setIsDragging(true);
  };

  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      if (!isDragging) return;

      const containerWidth = window.innerWidth;
      const newLeftWidth = (e.clientX / containerWidth) * 100;

      // Constrain between 30% and 70%
      if (newLeftWidth >= 30 && newLeftWidth <= 70) {
        setLeftPanelWidth(newLeftWidth);
      }
    };

    const handleMouseUp = () => {
      setIsDragging(false);
    };

    if (isDragging) {
      // Prevent text selection and change cursor globally during drag
      document.body.style.userSelect = 'none';
      document.body.style.cursor = 'col-resize';

      document.addEventListener("mousemove", handleMouseMove);
      document.addEventListener("mouseup", handleMouseUp);
    } else {
      // Restore normal state
      document.body.style.userSelect = '';
      document.body.style.cursor = '';
    }

    return () => {
      document.removeEventListener("mousemove", handleMouseMove);
      document.removeEventListener("mouseup", handleMouseUp);
      document.body.style.userSelect = '';
      document.body.style.cursor = '';
    };
  }, [isDragging]);

  const handleBuildAgent = async (workflow: any) => {
    // Use the yaml_config from the streamed workflow data
    const yamlContent = workflow.yaml_config;

    if (!yamlContent) {
      setErrorData({ title: "No YAML data available to build agent" });
      return;
    }

    try {
      // Store YAML for Specification tab
      setYamlSpec(yamlContent);

      // Convert spec to flow JSON
      const result = await convertSpecMutation.mutateAsync({
        spec_yaml: yamlContent,
      });

      if (result.success) {
        console.log("[AgentBuilder] Converted flow:", result.flow);

        // Create the flow in database
        const folderId = myCollectionId || folders?.[0]?.id || "";

        try {
          const createdFlow = await createFlowMutation.mutateAsync({
            name: workflow.metadata?.domain
              ? `${workflow.metadata.domain} Agent`
              : "Generated Agent",
            description: workflow.metadata
              ? `Auto-generated ${workflow.metadata.domain} agent for ${workflow.metadata.primary_task}`
              : "Agent created by AI Agent Builder",
            data: result.flow.data, // Extract just the data field (nodes/edges/viewport)
            is_component: false,
            folder_id: folderId,
            endpoint_name: undefined,
            icon: undefined,
            gradient: undefined,
            tags: undefined,
            mcp_enabled: undefined,
          });

          console.log("[AgentBuilder] Flow created:", createdFlow);

          // Store the created flow data and ID
          setFlowData(result.flow);
          setCreatedFlowId(createdFlow.id);
        } catch (flowError: any) {
          console.error("[AgentBuilder] Flow creation error:", flowError);
          console.error("[AgentBuilder] Flow data that failed:", result.flow);
          throw new Error(`Failed to create flow: ${flowError.response?.data?.detail || flowError.message}`);
        }
      }
    } catch (error: any) {
      console.error("[AgentBuilder] Build agent error:", error);
      setErrorData({
        title: "Failed to build agent",
        list: [error.message || "Unknown error"]
      });
    }
  };

  return (
    <div className="flex h-full w-full flex-col agent-builder-conversation-page">

      {/* Main Content - Always 2-column layout */}
      <div className="flex flex-1 overflow-hidden">
        {/* Chat Panel */}
        <div
          className="flex flex-col border-r"
          style={{ width: `${leftPanelWidth}%` }}
        >
          {/* Chat Messages Area */}
          <div className="flex-1 overflow-y-auto px-4 py-6">
            <div className="max-w-full">
              <StreamingMessages
                messages={messages}
                isLoading={isLoading}
                onBuildAgent={handleBuildAgent}
                onTriggerBuild={handleTriggerBuild}
                isFlowBuilt={!!createdFlowId}
              />
            </div>
          </div>

          {/* Input Section - Fixed at bottom */}
          <div className="border-t bg-background px-4 py-4">
            <div className="max-w-full">
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

        {/* Resizable Divider - Always visible */}
        <div
          className={`w-1 bg-border hover:bg-primary cursor-col-resize transition-colors ${
            isDragging ? 'bg-primary' : ''
          }`}
          onMouseDown={handleDragStart}
        />

        {/* Flow Panel - Right Side - Always visible */}
        <div
          className="bg-background overflow-hidden"
          style={{
            width: `${100 - leftPanelWidth}%`,
            pointerEvents: isDragging ? 'none' : 'auto', // Disable pointer events during drag
          }}
        >
          <FlowPanel
            flowId={createdFlowId}
            yamlSpec={yamlSpec}
            flowData={flowData}
            folderId={myCollectionId || folders?.[0]?.id || ""}
            onClose={() => setCreatedFlowId(null)}
          />
        </div>
      </div>
    </div>
  );
}
