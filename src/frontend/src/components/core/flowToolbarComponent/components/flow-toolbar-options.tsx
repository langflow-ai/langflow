import CollaborationFlowToolbar from "@/pages/FlowPage/components/CollaborationFlowToolbar";
import useFlowStore from "@/stores/flowStore";
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

  return (
    <div className="flex items-center gap-2">
      <CollaborationFlowToolbar />
      <PlaygroundButton hasIO={hasIO} />
      <PublishDropdown
        openApiModal={openApiModal}
        setOpenApiModal={setOpenApiModal}
      />
      <DeployButton />
    </div>
  );
};

export default FlowToolbarOptions;
