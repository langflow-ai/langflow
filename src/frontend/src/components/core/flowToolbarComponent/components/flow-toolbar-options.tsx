import { useState } from "react";
import useFlowStore from "@/stores/flowStore";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import PublishDropdown from "./deploy-dropdown";
import PlaygroundButton from "./playground-button";
import VersionDropdown from "./version-dropdown";
import { useCheckFlowPublished } from "@/controllers/API/queries/published-flows";

export default function FlowToolbarOptions() {
  const [open, setOpen] = useState<boolean>(false);
  const hasIO = useFlowStore((state) => state.hasIO);
  const currentFlowId = useFlowsManagerStore((state) => state.currentFlow?.id);

  // Check if flow is published to show version dropdown
  const { data: publishedData } = useCheckFlowPublished(currentFlowId);
  const isPublished = publishedData?.is_published || false;

  return (
    <div className="flex items-center gap-1.5">
      <div className="flex h-full w-full gap-1.5 rounded-sm transition-all">
        <PlaygroundButton
          hasIO={hasIO}
          open={open}
          setOpen={setOpen}
          canvasOpen
        />
      </div>

      {/* Version Dropdown - only show if flow is published */}
      {isPublished && currentFlowId && (
        <VersionDropdown flowId={currentFlowId} />
      )}

      <PublishDropdown />
    </div>
  );
}
