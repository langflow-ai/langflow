import ForwardedIconComponent from "@/components/common/genericIconComponent";
import GlobalVariableModal from "@/components/core/GlobalVariableModal/GlobalVariableModal";
import { CommandItem } from "@/components/ui/command";
import { LANGFLOW_ONLY_CANVAS } from "@/customization/feature-flags";
import { cn } from "@/utils/utils";

const GeneralGlobalVariableModal = () => {
  return (
    <>
      <GlobalVariableModal disabled={false || LANGFLOW_ONLY_CANVAS}>
        <CommandItem value="doNotFilter-addNewVariable">
          <ForwardedIconComponent
            name="Plus"
            className={cn("mr-2 h-4 w-4 text-primary")}
            aria-hidden="true"
          />
          <span>Add New Variable</span>
        </CommandItem>
      </GlobalVariableModal>
    </>
  );
};

export default GeneralGlobalVariableModal;
