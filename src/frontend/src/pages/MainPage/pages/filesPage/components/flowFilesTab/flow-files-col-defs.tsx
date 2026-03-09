import type { ColDef } from "ag-grid-community";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import type { FlowFileInfo } from "@/controllers/API/queries/file-management/use-get-flow-files";
import { formatFileSize } from "@/utils/stringManipulation";
import { FILE_ICONS } from "@/utils/styleUtils";
import { cn } from "@/utils/utils";

interface FlowFilesColDefsOptions {
  onDownload: (flowId: string, fileName: string) => void;
  onDelete: (file: FlowFileInfo) => void;
}

export const getFlowFilesColDefs = ({
  onDownload,
  onDelete,
}: FlowFilesColDefsOptions): ColDef[] => [
  {
    headerName: "File Name",
    field: "file_name",
    flex: 2,
    headerCheckboxSelection: true,
    checkboxSelection: true,
    filter: "agTextColumnFilter",
    cellRenderer: (params) => {
      const extension = params.value.split(".").pop()?.toLowerCase() ?? "";
      return (
        <div className="flex items-center gap-4 font-medium">
          <div className="file-icon pointer-events-none relative">
            <ForwardedIconComponent
              name={FILE_ICONS[extension]?.icon ?? "File"}
              className={cn(
                "-mx-[3px] h-6 w-6 shrink-0",
                FILE_ICONS[extension]?.color ?? undefined,
              )}
            />
          </div>
          <span className="text-sm font-medium">{params.value}</span>
        </div>
      );
    },
  },
  {
    headerName: "Type",
    field: "file_name",
    flex: 1,
    filter: "agTextColumnFilter",
    editable: false,
    valueFormatter: (params) => {
      return params.value.split(".").pop()?.toUpperCase() ?? "";
    },
    cellClass: "text-muted-foreground cursor-text select-text",
  },
  {
    headerName: "Flow",
    field: "flow_name",
    flex: 1,
    filter: "agTextColumnFilter",
    cellClass: "text-muted-foreground cursor-text select-text",
  },
  {
    headerName: "Size",
    field: "file_size",
    flex: 1,
    valueFormatter: (params) => formatFileSize(params.value),
    cellClass: "text-muted-foreground",
  },
  {
    maxWidth: 60,
    editable: false,
    resizable: false,
    cellClass: "cursor-default",
    cellRenderer: (params) => {
      return (
        <div className="flex h-full cursor-default items-center justify-center">
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="ghost" size="iconMd">
                <ForwardedIconComponent name="EllipsisVertical" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent
              sideOffset={0}
              side="bottom"
              className="-ml-24"
            >
              <DropdownMenuItem
                onClick={(event) => {
                  event.stopPropagation();
                  onDownload(params.data.flow_id, params.data.file_name);
                }}
                className="cursor-pointer"
              >
                <ForwardedIconComponent
                  name="Download"
                  aria-hidden="true"
                  className="mr-2 h-4 w-4"
                />
                Download
              </DropdownMenuItem>
              <DropdownMenuItem
                onClick={(event) => {
                  event.stopPropagation();
                  onDelete(params.data);
                }}
                className="cursor-pointer text-destructive"
              >
                <ForwardedIconComponent
                  name="Trash2"
                  aria-hidden="true"
                  className="mr-2 h-4 w-4"
                />
                Delete
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      );
    },
  },
];
