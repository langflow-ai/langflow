import ForwardedIconComponent from "@/components/common/genericIconComponent";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { ReactNode } from "react";

export default function FilesContextMenuComponent({
  children,
  isLocal,
  handleSelectOptionsChange,
}: {
  children: ReactNode;
  isLocal: boolean;
  handleSelectOptionsChange: (option: string) => void;
}) {
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>{children}</DropdownMenuTrigger>
      <DropdownMenuContent sideOffset={5} side="bottom">
        <DropdownMenuItem
          onClick={(e) => {
            e.stopPropagation();
            handleSelectOptionsChange("rename");
          }}
          className="cursor-pointer"
          data-testid="btn-edit-flow"
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
            handleSelectOptionsChange("export");
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
