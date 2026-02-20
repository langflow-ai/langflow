import IconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import { useCustomNavigate } from "@/customization/hooks/use-custom-navigate";
import useFlowStore from "@/stores/flowStore";
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
  const navigate = useCustomNavigate();

  return (
    <div className="flex items-center gap-1">
      <PlaygroundButton hasIO={hasIO} />
      <PublishDropdown
        openApiModal={openApiModal}
        setOpenApiModal={setOpenApiModal}
      />
      <Button
        variant="secondary"
        size="md"
        className="!px-2.5 font-normal"
        onClick={() => navigate("/all")}
        data-testid="deploy-button"
      >
        Deploy
        <IconComponent name="EllipsisVertical" className="!h-4 !w-4" />
      </Button>
    </div>
  );
};

export default FlowToolbarOptions;
