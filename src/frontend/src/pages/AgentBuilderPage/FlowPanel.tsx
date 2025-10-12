import { useState } from "react";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import SpecificationView from "./SpecificationView";
import FlowPage from "../FlowPage";

interface FlowPanelProps {
  flowId: string | null;
  yamlSpec: string;
  flowData: any;
  folderId: string;
  onClose: () => void;
}

export default function FlowPanel({ flowId, yamlSpec, flowData, folderId, onClose }: FlowPanelProps) {
  const [activeTab, setActiveTab] = useState<"specification" | "visualization">("visualization");
  const isDisabled = !flowId;

  return (
    <div className="h-full flex flex-col bg-background">
      {/* Header */}
      <div className="border-b px-4 py-3 flex items-center justify-between">
        <h3 className="font-semibold">Agent Flow</h3>
        {!isDisabled && (
          <button
            onClick={onClose}
            className="text-muted-foreground hover:text-foreground"
            aria-label="Close panel"
          >
            <ForwardedIconComponent name="X" className="h-4 w-4" />
          </button>
        )}
      </div>

      {/* Tabs */}
      <div className="border-b">
        <div className="flex px-4">
          <button
            onClick={() => !isDisabled && setActiveTab("visualization")}
            disabled={isDisabled}
            className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
              isDisabled
                ? "border-transparent text-muted-foreground/50 cursor-not-allowed"
                : activeTab === "visualization"
                ? "border-primary text-primary"
                : "border-transparent text-muted-foreground hover:text-foreground"
            }`}
          >
            <ForwardedIconComponent name="Layers" className="h-4 w-4 inline-block mr-2" />
            Flow Visualization
          </button>
          <button
            onClick={() => !isDisabled && setActiveTab("specification")}
            disabled={isDisabled}
            className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
              isDisabled
                ? "border-transparent text-muted-foreground/50 cursor-not-allowed"
                : activeTab === "specification"
                ? "border-primary text-primary"
                : "border-transparent text-muted-foreground hover:text-foreground"
            }`}
          >
            <ForwardedIconComponent name="FileText" className="h-4 w-4 inline-block mr-2" />
            Specification
          </button>
        </div>
      </div>

      {/* Tab Content */}
      <div className="flex-1 overflow-hidden">
        {activeTab === "specification" && (
          <>
            {isDisabled ? (
              <div className="flex items-center justify-center h-full p-8 text-center">
                <div className="max-w-md">
                  <ForwardedIconComponent
                    name="FileText"
                    className="h-16 w-16 mx-auto mb-4 text-muted-foreground/30"
                  />
                  <p className="text-sm text-muted-foreground">
                    Build your agent to see the specification here.
                  </p>
                </div>
              </div>
            ) : (
              <SpecificationView flowData={flowData} yamlSpec={yamlSpec} />
            )}
          </>
        )}

        {activeTab === "visualization" && (
          <>
            {isDisabled ? (
              <div className="flex items-center justify-center h-full p-8 text-center">
                <div className="max-w-md">
                  <ForwardedIconComponent
                    name="Workflow"
                    className="h-16 w-16 mx-auto mb-4 text-muted-foreground/30"
                  />
                  <p className="text-sm text-muted-foreground">
                    Build your agent to see the flow visualization here.
                  </p>
                </div>
              </div>
            ) : (
              <div className="h-full agent-builder-flow-view">
                {/* Direct canvas component without iframe */}
                <FlowPage view={true} flowId={flowId} folderId={folderId} />
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
