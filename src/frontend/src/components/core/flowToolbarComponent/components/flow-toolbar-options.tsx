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

  return (
    <PermissionsProvider
      resourceType="flow"
      resourceIds={currentFlowId ? [currentFlowId] : []}
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
