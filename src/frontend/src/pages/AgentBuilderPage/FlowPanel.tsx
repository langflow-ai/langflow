import { useState } from "react";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import SpecificationView from "./SpecificationView";

interface FlowPanelProps {
  flowId: string;
  yamlSpec: string;
  flowData: any;
  folderId: string;
  onClose: () => void;
}

export default function FlowPanel({ flowId, yamlSpec, flowData, folderId, onClose }: FlowPanelProps) {
  const [activeTab, setActiveTab] = useState<"specification" | "visualization">("visualization");

  // Construct the flow URL
  const flowUrl = `/flow/${flowId}/folder/${folderId}/`;

  return (
    <div className="h-full flex flex-col bg-background">
      {/* Header */}
      <div className="border-b px-4 py-3 flex items-center justify-between">
        <h3 className="font-semibold">Agent Flow</h3>
        <button
          onClick={onClose}
          className="text-muted-foreground hover:text-foreground"
          aria-label="Close panel"
        >
          <ForwardedIconComponent name="X" className="h-4 w-4" />
        </button>
      </div>

      {/* Tabs */}
      <div className="border-b">
        <div className="flex px-4">
          <button
            onClick={() => setActiveTab("specification")}
            className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
              activeTab === "specification"
                ? "border-primary text-primary"
                : "border-transparent text-muted-foreground hover:text-foreground"
            }`}
          >
            Specification
          </button>
          <button
            onClick={() => setActiveTab("visualization")}
            className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
              activeTab === "visualization"
                ? "border-primary text-primary"
                : "border-transparent text-muted-foreground hover:text-foreground"
            }`}
          >
            Flow Visualization
          </button>
        </div>
      </div>

      {/* Tab Content */}
      <div className="flex-1 overflow-hidden">
        {activeTab === "specification" && (
          <SpecificationView flowData={flowData} />
        )}

        {activeTab === "visualization" && (
          <div className="h-full">
            {/* Embed flow editor using iframe */}
            <iframe
              src={flowUrl}
              className="w-full h-full border-0"
              title="Flow Visualization"
            />
          </div>
        )}
      </div>
    </div>
  );
}
