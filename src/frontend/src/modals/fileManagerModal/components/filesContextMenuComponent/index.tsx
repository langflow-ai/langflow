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
import { FileType } from "@/types/file_management";
import { ReactNode } from "react";

export default function FilesContextMenuComponent({
  children,
  file,
}: {
  children: ReactNode;
  file: FileType;
}) {
  const isLocal = file.provider == null;

  const { mutate: downloadFile } = useGetDownloadFileV2({
    id: file.id,
    filename: file.name,
  });

  const { mutate: deleteFile } = useDeleteFileV2({
    id: file.id,
  });

  const { mutate: duplicateFile } = useDuplicateFileV2({
    id: file.id,
    filename: file.name,
  });

  const handleSelectOptionsChange = (option: string) => {
    switch (option) {
      case "rename":
        console.log("rename");
        break;
      case "replace":
        console.log("replace");
        break;
      case "download":
        downloadFile();
        break;
      case "delete":
        deleteFile();
        break;
      case "duplicate":
        duplicateFile();
        break;
    }
  };

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>{children}</DropdownMenuTrigger>
      <DropdownMenuContent sideOffset={0} side="bottom" className="-ml-24">
        <DropdownMenuItem
          onClick={(e) => {
            e.stopPropagation();
            handleSelectOptionsChange("rename");
          }}
          className="cursor-pointer"
          data-testid="btn-edit-flow"
        >
          <ForwardedIconComponent
            name="FilePen"
            aria-hidden="true"
            className="mr-2 h-4 w-4"
          />
          Rename
        </DropdownMenuItem>
        <DropdownMenuItem
          onClick={(e) => {
            e.stopPropagation();
            handleSelectOptionsChange("replace");
          }}
          className="cursor-pointer"
          data-testid="btn-edit-flow"
        >
          <ForwardedIconComponent
            name="Replace"
            aria-hidden="true"
            className="mr-2 h-4 w-4"
          />
          Replace
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
        <DropdownMenuItem
          onClick={(e) => {
            e.stopPropagation();
            handleSelectOptionsChange("delete");
          }}
          className="cursor-pointer text-destructive"
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
  );
}
