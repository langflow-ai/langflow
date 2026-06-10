import { PermissionsProvider } from "@/contexts/permissionsContext";
import useFlowStore from "@/stores/flowStore";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import DeployButton from "./deploy-button";
import PublishDropdown from "./deploy-dropdown";
import PlaygroundButton from "./playground-button";

type FlowToolbarOptionsProps = {
  openApiModal: boolean;
  setOpenApiModal: (open: boolean | ((prev: boolean) => boolean)) => void;
};
const FlowToolbarOptions = ({
  openApiModal,
  setOpenApiModal,
}: FlowToolbarOptionsProps) => {
  const hasIO = useFlowStore((state) => state.hasIO);
  const currentFlowId = useFlowsManagerStore((state) => state.currentFlowId);
  // Scope to the flow's project so the toolbar evaluates the same
  // domain-scoped permission set as the project list (HomePage).
  const currentFlowFolderId = useFlowsManagerStore(
    (state) => state.currentFlow?.folder_id,
  );

  return (
    <PermissionsProvider
      resourceType="flow"
      resourceIds={currentFlowId ? [currentFlowId] : []}
      domain={
        currentFlowFolderId ? `project:${currentFlowFolderId}` : undefined
      }
    >
      <div className="flex items-center gap-1">
        <PlaygroundButton hasIO={hasIO} />
        <PublishDropdown
          openApiModal={openApiModal}
          setOpenApiModal={setOpenApiModal}
        />
        <DeployButton />
      </div>
    </PermissionsProvider>
  );
};

export default FlowToolbarOptions;
