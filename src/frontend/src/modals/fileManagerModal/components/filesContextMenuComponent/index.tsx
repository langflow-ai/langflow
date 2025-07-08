import ForwardedIconComponent from "@/components/common/genericIconComponent";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { useGetDownloadFileV2 } from "@/controllers/API/queries/file-management";
import { useDeleteFileV2 } from "@/controllers/API/queries/file-management/use-delete-file";
import { useDuplicateFileV2 } from "@/controllers/API/queries/file-management/use-duplicate-file";
import ConfirmationModal from "@/modals/confirmationModal";
import useAlertStore from "@/stores/alertStore";
import { FileType } from "@/types/file_management";
import { ReactNode, useState } from "react";

export default function FilesContextMenuComponent({
  children,
  file,
  handleRename,
  simplified,
}: {
  children: ReactNode;
  file: FileType;
  handleRename: (id: string, name: string) => void;
  simplified?: boolean;
}) {
  const isLocal = file.provider == null;
  const [showDeleteConfirmation, setShowDeleteConfirmation] = useState(false);

  const setSuccessData = useAlertStore((state) => state.setSuccessData);

  const { mutate: downloadFile } = useGetDownloadFileV2({
    id: file.id,
    filename: file.name,
    type: file.path.split(".").pop() || "",
  });

  const { mutate: deleteFile } = useDeleteFileV2({
    id: file.id,
  });

  const { mutate: duplicateFile } = useDuplicateFileV2({
    id: file.id,
    filename: file.name,
    type: file.path.split(".").pop() || "",
  });

  const handleSelectOptionsChange = (option: string) => {
    switch (option) {
      case "rename":
        handleRename(file.id, file.name);
        break;
      case "replace":
        console.log("replace");
        break;
      case "download":
        downloadFile();
        break;
      case "delete":
        setShowDeleteConfirmation(true);
        break;
      case "duplicate":
        duplicateFile();
        break;
    }
  };

  return (
    <>
      <DropdownMenu>
        <DropdownMenuTrigger asChild>{children}</DropdownMenuTrigger>
        <DropdownMenuContent sideOffset={0} side="bottom" className="-ml-24">
          <DropdownMenuItem
            onClick={(e) => {
              e.stopPropagation();
              handleSelectOptionsChange("rename");
            }}
            className="cursor-pointer"
            data-testid="btn-rename-file"
          >
            <ForwardedIconComponent
              name="SquarePen"
              aria-hidden="true"
              className="mr-2 h-4 w-4"
            />
            Rename
          </DropdownMenuItem>
          <DropdownMenuItem
            onClick={(e) => {
              e.stopPropagation();
              handleSelectOptionsChange("download");
            }}
            className="cursor-pointer"
            data-testid="btn-download-json"
          >
            <ForwardedIconComponent
              name="Download"
              aria-hidden="true"
              className="mr-2 h-4 w-4"
            />
            Download
          </DropdownMenuItem>
          {!simplified && (
            <DropdownMenuItem
              onClick={(e) => {
                e.stopPropagation();
                handleSelectOptionsChange("duplicate");
              }}
              className="cursor-pointer"
              data-testid="btn-duplicate-flow"
            >
              <ForwardedIconComponent
                name="CopyPlus"
                aria-hidden="true"
                className="mr-2 h-4 w-4"
              />
              Duplicate
            </DropdownMenuItem>
          )}
          <DropdownMenuItem
            onClick={(e) => {
              e.stopPropagation();
              handleSelectOptionsChange("delete");
            }}
            className="text-destructive cursor-pointer"
            data-testid="btn-delete-file"
          >
            <ForwardedIconComponent
              name={isLocal ? "Trash2" : "ListX"}
              aria-hidden="true"
              className="mr-2 h-4 w-4"
            />
            {isLocal ? "Delete" : "Remove"}
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
      <ConfirmationModal
        open={showDeleteConfirmation}
        onClose={() => setShowDeleteConfirmation(false)}
        onCancel={() => setShowDeleteConfirmation(false)}
        title={isLocal ? "Delete File" : "Remove File"}
        titleHeader={`Are you sure you want to ${isLocal ? "delete" : "remove"} "${file.name}"?`}
        cancelText="Cancel"
        size="x-small"
        confirmationText={isLocal ? "Delete" : "Remove"}
        icon={isLocal ? "Trash2" : "ListX"}
        destructive
        onConfirm={() => {
          deleteFile();
          setSuccessData({
            title: "The file has been deleted successfully",
          });
          setShowDeleteConfirmation(false);
        }}
      >
        <ConfirmationModal.Content>
          <div className="text-muted-foreground text-sm">
            {isLocal
              ? "This action cannot be undone. The file will be permanently deleted."
              : "This will remove the file from your list. You can add it back later if needed."}
          </div>
        </ConfirmationModal.Content>
      </ConfirmationModal>
    </>
  );
}
