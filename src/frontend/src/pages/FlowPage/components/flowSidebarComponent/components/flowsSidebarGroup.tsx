import { memo, useMemo } from "react";
import {
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarMenu,
} from "@/components/ui/sidebar";
import { useGetFlow } from "@/controllers/API/queries/flows/use-get-flow";
import { useFolderStore } from "@/stores/foldersStore";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import type { FlowType } from "../../../../../types/flow";
import FlowDraggableComponent from "./flowDraggableComponent";
import { SearchConfigTrigger } from "./searchConfigTrigger";

interface FlowsSidebarGroupProps {
  nodeColors: any;
  onDragStart: (
    event: React.DragEvent<any>,
    data: { type: string; node?: any }
  ) => void;
  openCategories: string[];
  setOpenCategories: (categories: string[]) => void;
  search: string;
  showSearchConfigTrigger?: boolean;
  showConfig: boolean;
  setShowConfig: (show: boolean) => void;
}

export default memo(function FlowsSidebarGroup({
  nodeColors,
  onDragStart,
  openCategories,
  setOpenCategories,
  search,
  showSearchConfigTrigger = false,
  showConfig,
  setShowConfig,
}: FlowsSidebarGroupProps) {
  const flows = useFlowsManagerStore((state) => state.flows);
  const currentFlow = useFlowsManagerStore((state) => state.currentFlow);
  const folders = useFolderStore((state) => state.folders);
  const { mutateAsync: getFlow } = useGetFlow();

  // Get flows from the same project/folder as the current flow
  const currentProjectFlows = useMemo(() => {
    if (!currentFlow?.folder_id || !flows) return [];

    // Filter flows that belong to the same folder and exclude the current flow
    return flows.filter(
      (flow) => 
        flow.folder_id === currentFlow.folder_id && 
        flow.id !== currentFlow.id
    );
  }, [flows, currentFlow]);

  // Get current folder info for display
  const currentFolder = useMemo(() => {
    if (!currentFlow?.folder_id || !folders) return null;
    return folders.find((folder) => folder.id === currentFlow.folder_id);
  }, [folders, currentFlow]);

  // Filter flows based on search
  const filteredFlows = useMemo(() => {
    if (!search) return currentProjectFlows;
    
    return currentProjectFlows.filter((flow) =>
      flow.name.toLowerCase().includes(search.toLowerCase()) ||
      flow.description?.toLowerCase().includes(search.toLowerCase())
    );
  }, [currentProjectFlows, search]);

  const handleFlowDragStart = (event: React.DragEvent, flow: FlowType) => {
    // Create drag preview
    var crt = event.currentTarget.cloneNode(true);
    crt.style.position = "absolute";
    crt.style.width = "215px";
    crt.style.top = "-500px";
    crt.style.right = "-500px";
    crt.classList.add("cursor-grabbing");
    document.body.appendChild(crt);
    event.dataTransfer.setDragImage(crt, 0, 0);
    
    // Set drag data with flow information (data will be fetched in drop handler if needed)
    const flowData = {
      type: "flow_data",
      flow: flow
    };
    event.dataTransfer.setData("application/reactflow", JSON.stringify(flowData));
  };

  if (!currentFlow?.folder_id || filteredFlows.length === 0) {
    return null;
  }

  const flowColor = nodeColors["flow"] || "#6366f1";

  return (
    <SidebarGroup className="p-3">
      <SidebarGroupLabel className="cursor-default flex items-center justify-between">
        <span>Flows {currentFolder ? `(${currentFolder.name})` : ""}</span>
        {showSearchConfigTrigger && (
          <SearchConfigTrigger
            showConfig={showConfig}
            setShowConfig={setShowConfig}
          />
        )}
      </SidebarGroupLabel>
      
      <SidebarGroupContent>
        <SidebarMenu>
          {filteredFlows.map((flow) => (
            <FlowDraggableComponent
              key={flow.id}
              sectionName="flows"
              display_name={flow.name}
              icon={flow.icon || "workflow"}
              itemName={flow.name}
              error={false}
              color={flowColor}
              onDragStart={(event) => handleFlowDragStart(event, flow)}
              flow={flow}
              official={false}
            />
          ))}
        </SidebarMenu>
      </SidebarGroupContent>
    </SidebarGroup>
  );
});