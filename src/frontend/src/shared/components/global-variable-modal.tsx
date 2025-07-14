import ForwardedIconComponent from "@/components/common/genericIconComponent";
import GlobalVariableModal from "@/components/core/GlobalVariableModal/GlobalVariableModal";
import { CommandItem } from "@/components/ui/command";
import { cn } from "@/utils/utils";

interface GeneralGlobalVariableModalProps {}

const GeneralGlobalVariableModal = ({}: GeneralGlobalVariableModalProps) => {
  return (
    <>
      <GlobalVariableModal disabled={false}>
        <CommandItem value="doNotFilter-addNewVariable">
          <ForwardedIconComponent
            name="Plus"
            className={cn("text-primary mr-2 h-4 w-4")}
            aria-hidden="true"
          />
          <span>Add New Variable</span>
        </CommandItem>
      </GlobalVariableModal>
    </>
  );
};

export default GeneralGlobalVariableModal;
