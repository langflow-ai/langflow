import { type ReactNode, useState } from "react";
import { useTranslation } from "react-i18next";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { useDeleteFileV2 } from "@/controllers/API/queries/file-management/use-delete-file";
import { useDuplicateFileV2 } from "@/customization/hooks/use-custom-duplicate-file";
import { useCustomHandleSingleFileDownload } from "@/customization/hooks/use-custom-handle-single-file-download";
import ConfirmationModal from "@/modals/confirmationModal";
import useAlertStore from "@/stores/alertStore";
import type { FileType } from "@/types/file_management";

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
  const { t } = useTranslation();
  const isLocal = file.provider == null;
  const [showDeleteConfirmation, setShowDeleteConfirmation] = useState(false);

  const setSuccessData = useAlertStore((state) => state.setSuccessData);

  const { handleSingleDownload } = useCustomHandleSingleFileDownload(file);

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
        // TODO: Implement replace file
        console.warn("replace");
        break;
      case "download":
        handleSingleDownload();
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
            {t("files.rename")}
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
            {t("files.download")}
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
              {t("files.duplicate")}
            </DropdownMenuItem>
          )}
          <DropdownMenuItem
            onClick={(e) => {
              e.stopPropagation();
              handleSelectOptionsChange("delete");
            }}
            className="cursor-pointer text-destructive"
            data-testid="btn-delete-file"
          >
            <ForwardedIconComponent
              name={isLocal ? "Trash2" : "ListX"}
              aria-hidden="true"
              className="mr-2 h-4 w-4"
            />
            {isLocal ? t("files.delete") : t("files.remove")}
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
      <ConfirmationModal
        open={showDeleteConfirmation}
        onClose={() => setShowDeleteConfirmation(false)}
        onCancel={() => setShowDeleteConfirmation(false)}
        title={
          isLocal ? t("files.deleteFileTitle") : t("files.removeFileTitle")
        }
        titleHeader={
          isLocal
            ? t("files.deleteFileConfirm", { name: file.name })
            : t("files.removeFileConfirm", { name: file.name })
        }
        cancelText={t("files.cancel")}
        size="x-small"
        confirmationText={isLocal ? t("files.delete") : t("files.remove")}
        icon={isLocal ? "Trash2" : "ListX"}
        destructive
        onConfirm={() => {
          deleteFile();
          setSuccessData({
            title: t("files.deleteFileSuccess"),
          });
          setShowDeleteConfirmation(false);
        }}
      >
        <ConfirmationModal.Content>
          <div className="text-sm text-muted-foreground">
            {isLocal
              ? t("files.deleteFilePermanent")
              : t("files.removeFileDescription")}
          </div>
        </ConfirmationModal.Content>
      </ConfirmationModal>
    </>
  );
}
