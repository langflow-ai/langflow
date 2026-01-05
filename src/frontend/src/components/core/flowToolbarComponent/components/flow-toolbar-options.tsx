import type { Dispatch, SetStateAction } from "react";
import useFlowStore from "@/stores/flowStore";
import PublishDropdown from "./deploy-dropdown";
import PlaygroundButton from "./playground-button";

type FlowToolbarOptionsProps = {
  open: boolean;
  setOpen: Dispatch<SetStateAction<boolean>>;
  openApiModal: boolean;
  setOpenApiModal: Dispatch<SetStateAction<boolean>>;
};
const FlowToolbarOptions = ({
  open,
  setOpen,
  openApiModal,
  setOpenApiModal,
}: FlowToolbarOptionsProps) => {
  const hasIO = useFlowStore((state) => state.hasIO);

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
      <PublishDropdown
        openApiModal={openApiModal}
        setOpenApiModal={setOpenApiModal}
      />
    </div>
  );
};

export default FlowToolbarOptions;
