import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import DeleteConfirmationModal from "@/modals/deleteConfirmationModal";
import { cn } from "@/utils/utils";

interface BulkActionsProps {
  selectedFlows: string[];
  onDownload: () => void;
  onDelete: () => void;
  isDownloading: boolean;
  isDeleting: boolean;
}

const BulkActions = ({
  selectedFlows,
  onDownload,
  onDelete,
  isDownloading,
  isDeleting,
}: BulkActionsProps) => {
  const hasSelection = selectedFlows.length > 0;
  const isMultiple = selectedFlows.length > 1;

  return (
    <div
      className={cn(
        "flex w-0 items-center gap-2 overflow-hidden opacity-0 transition-all duration-300",
        hasSelection && "w-36 opacity-100",
      )}
    >
      <Button
        variant="outline"
        size="iconMd"
        className="h-8 w-8"
        data-testid="download-bulk-btn"
        onClick={onDownload}
        loading={isDownloading}
        tabIndex={hasSelection ? 0 : -1}
      >
        <ForwardedIconComponent name="Download" />
      </Button>
      <DeleteConfirmationModal
        asChild
        onConfirm={onDelete}
        description={"flow" + (isMultiple ? "s" : "")}
        note={"and " + (isMultiple ? "their" : "its") + " message history"}
      >
        <Button
          variant="destructive"
          size="iconMd"
          className="px-2.5 !text-mmd"
          data-testid="delete-bulk-btn"
          loading={isDeleting}
          tabIndex={hasSelection ? 0 : -1}
        >
          <ForwardedIconComponent name="Trash2" />
          Delete
        </Button>
      </DeleteConfirmationModal>
    </div>
  );
};

export default BulkActions;
