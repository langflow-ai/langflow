import useFlowStore from "@/stores/flowStore";
import PublishDropdown from "./deploy-dropdown";
import EvaluateButton from "./evaluate-button";
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
    <div className="flex items-center gap-1">
      <PlaygroundButton hasIO={hasIO} />
      <EvaluateButton />
      <PublishDropdown
        openApiModal={openApiModal}
        setOpenApiModal={setOpenApiModal}
      />
    </div>
  );
};

export default FlowToolbarOptions;
