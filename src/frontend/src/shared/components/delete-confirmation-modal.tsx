import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import { ICON_STROKE_WIDTH } from "@/constants/constants";
import DeleteConfirmationModal from "@/modals/deleteConfirmationModal";
import { cn } from "@/utils/utils";

interface GeneralDeleteConfirmationModalProps {
  option: string;
}

const GeneralDeleteConfirmationModal = ({
  option,
}: GeneralDeleteConfirmationModalProps) => {
  return (
    <>
      <DeleteConfirmationModal
        onConfirm={(e) => {
          e.stopPropagation();
          e.preventDefault();
        }}
        description={'variable "' + option + '"'}
        asChild
      >
        <button
          onClick={(e) => {
            e.stopPropagation();
          }}
          className="pr-1"
        >
          <ForwardedIconComponent
            name="Trash2"
            className={cn(
              "h-4 w-4 text-primary opacity-0 hover:text-status-red group-hover:opacity-100",
            )}
            aria-hidden="true"
          />
        </button>
      </DeleteConfirmationModal>
    </>
  );
};

export default GeneralDeleteConfirmationModal;
