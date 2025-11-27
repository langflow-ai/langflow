import type { Dispatch, SetStateAction } from "react";
// NOTE: Changes commented out just for review, will be reverted when approved before merging
// so it won't affect the current implementation
// OLD: Modal-based playground button
// import PlaygroundButton from "./playground-button";
// NEW: Sliding container playground button
import { PlaygroundButtonSliding } from "@/customization/components/custom-playground-button-sliding";
import useFlowStore from "@/stores/flowStore";
import PublishDropdown from "./deploy-dropdown";

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
        {/* NOTE: Changes commented out just for review, will be reverted when approved before merging
            so it won't affect the current implementation */}
        {/* OLD: Modal-based implementation - commented out */}
        {/* <PlaygroundButton
          hasIO={hasIO}
          open={open}
          setOpen={setOpen}
          canvasOpen
        /> */}
        {/* NEW: Sliding container implementation */}
        <PlaygroundButtonSliding hasIO={hasIO} />
      </div>
      <PublishDropdown
        openApiModal={openApiModal}
        setOpenApiModal={setOpenApiModal}
      />
    </div>
  );
};

export default FlowToolbarOptions;
