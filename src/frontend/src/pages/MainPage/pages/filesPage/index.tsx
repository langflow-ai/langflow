import ForwardedIconComponent from "@/components/common/genericIconComponent";
import ShadTooltip from "@/components/common/shadTooltipComponent";
import CardsWrapComponent from "@/components/core/cardsWrapComponent";
import TableComponent from "@/components/core/parameterRenderComponent/components/tableComponent";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import Loading from "@/components/ui/loading";
import { SidebarTrigger } from "@/components/ui/sidebar";
import {
  useGetFilesV2,
  usePostUploadFileV2,
} from "@/controllers/API/queries/file-management";
import { usePostRenameFileV2 } from "@/controllers/API/queries/file-management/use-put-rename-file";
import useUploadFile from "@/hooks/files/use-upload-file";
import FilesContextMenuComponent from "@/modals/fileManagerModal/components/filesContextMenuComponent";
import useAlertStore from "@/stores/alertStore";
import { formatFileSize } from "@/utils/stringManipulation";
import { FILE_ICONS } from "@/utils/styleUtils";
import { cn } from "@/utils/utils";
import { ColDef, NewValueParams } from "ag-grid-community";
import { AgGridReact } from "ag-grid-react";
import { useMemo, useRef, useState } from "react";
import { sortByDate } from "../../utils/sort-flows";
import DragWrapComponent from "./components/dragWrapComponent";

export const FilesPage = () => {
  const tableRef = useRef<AgGridReact<any>>(null);
  const { data: files } = useGetFilesV2();
  const setErrorData = useAlertStore((state) => state.setErrorData);
  const setSuccessData = useAlertStore((state) => state.setSuccessData);

  const { mutate: rename } = usePostRenameFileV2();

  const handleRename = (params: NewValueParams<any, any>) => {
    rename({
      id: params.data.id,
      name: params.newValue,
    });
  };

  const handleOpenRename = (id: string, name: string) => {
    if (tableRef.current) {
      tableRef.current.api.startEditingCell({
        rowIndex: files?.findIndex((file) => file.id === id) ?? 0,
        colKey: "name",
      });
    }
  };

  const uploadFile = useUploadFile({ multiple: true });

  const handleUpload = async (files?: File[]) => {
    try {
      const filesIds = await uploadFile({
        files: files,
      });
      setSuccessData({
        title: `File${filesIds.length > 1 ? "s" : ""} uploaded successfully`,
      });
    } catch (error: any) {
      setErrorData({
        title: "Error uploading file",
        list: [error.message || "An error occurred while uploading the file"],
      });
    }
  };

  const { mutate: uploadFileDirect } = usePostUploadFileV2();

  const colDefs: ColDef[] = [
    {
      headerName: "Name",
      field: "name",
      flex: 2,
      editable: true,
      filter: "agTextColumnFilter",
      cellClass: "cursor-text select-text",
      cellRenderer: (params) => {
        const type = params.data.path.split(".")[1]?.toLowerCase();
        return (
          <div className="flex items-center gap-2 font-medium">
            {params.data.progress !== undefined &&
            params.data.progress !== -1 ? (
              <div className="flex h-6 items-center justify-center text-xs font-semibold text-muted-foreground">
                {Math.round(params.data.progress * 100)}%
              </div>
            ) : (
              <ForwardedIconComponent
                name={FILE_ICONS[type]?.icon ?? "File"}
                className={cn(
                  "h-6 w-6 shrink-0",
                  params.data.progress !== undefined
                    ? "text-placeholder-foreground"
                    : (FILE_ICONS[type]?.color ?? undefined),
                )}
              />
            )}
            <div
              className={cn(
                "flex cursor-text items-center gap-2 text-sm font-medium",
                params.data.progress !== undefined &&
                  params.data.progress === -1 &&
                  "pointer-events-none text-placeholder-foreground",
              )}
            >
              {params.value}.{type}
            </div>
            {params.data.progress !== undefined &&
            params.data.progress === -1 ? (
              <span className="text-[13px] text-primary">
                Upload failed,{" "}
                <span
                  className="cursor-pointer text-accent-pink-foreground underline"
                  onClick={(e) => {
                    e.stopPropagation();
                    if (params.data.file) {
                      uploadFileDirect({ file: params.data.file });
                    }
                  }}
                >
                  try again?
                </span>
              </span>
            ) : (
              <></>
            )}
          </div>
        );
      }, //This column will be twice as wide as the others
    }, //This column will be twice as wide as the others
    {
      headerName: "Type",
      field: "path",
      flex: 1,
      filter: "agTextColumnFilter",
      editable: false,
      valueFormatter: (params) => {
        return params.value.split(".")[1]?.toUpperCase();
      },
      cellClass: "text-muted-foreground cursor-text select-text",
    },
    {
      headerName: "Size",
      field: "size",
      flex: 1,
      valueFormatter: (params) => {
        return formatFileSize(params.value);
      },
      editable: false,
      cellClass: "text-muted-foreground cursor-text select-text",
    },
    {
      headerName: "Modified",
      field: "updated_at",
      valueFormatter: (params) => {
        return params.data.progress
          ? ""
          : new Date(params.value + "Z").toLocaleString();
      },
      editable: false,
      flex: 1,
      resizable: false,
      cellClass: "text-muted-foreground cursor-text select-text",
    },
    {
      maxWidth: 60,
      editable: false,
      resizable: false,
      cellClass: "cursor-default",
      cellRenderer: (params) => {
        return (
          <div className="flex h-full cursor-default items-center justify-center">
            {!params.data.progress && (
              <FilesContextMenuComponent
                file={params.data}
                handleRename={handleOpenRename}
              >
                <Button variant="ghost" size="iconMd">
                  <ForwardedIconComponent name="EllipsisVertical" />
                </Button>
              </FilesContextMenuComponent>
            )}
          </div>
        );
      },
    },
  ];

  const onFileDrop = async (e: React.DragEvent) => {
    e.preventDefault;
    e.stopPropagation();
    const droppedFiles = Array.from(e.dataTransfer.files);
    if (droppedFiles.length > 0) {
      await handleUpload(droppedFiles);
    }
  };

  const UploadButtonComponent = useMemo(() => {
    return (
      <ShadTooltip content="Upload File" side="bottom">
        <Button
          className="!px-3 md:!px-4 md:!pl-3.5"
          onClick={async () => {
            await handleUpload();
          }}
          id="upload-file-btn"
          data-testid="upload-file-btn"
        >
          <ForwardedIconComponent
            name="Plus"
            aria-hidden="true"
            className="h-4 w-4"
          />
          <span className="hidden whitespace-nowrap font-semibold md:inline">
            Upload
          </span>
        </Button>
      </ShadTooltip>
    );
  }, [uploadFile]);

  const [quickFilterText, setQuickFilterText] = useState("");
  return (
    <div
      className="flex h-full w-full flex-col overflow-y-auto"
      data-testid="cards-wrapper"
    >
      <div className="flex h-full w-full flex-col xl:container">
        <div className="flex flex-1 flex-col justify-start px-5 pt-10">
          <div className="flex h-full flex-col justify-start">
            <div
              className="flex items-center pb-8 text-xl font-semibold"
              data-testid="mainpage_title"
            >
              <div className="h-7 w-10 transition-all group-data-[open=true]/sidebar-wrapper:md:w-0 lg:hidden">
                <div className="relative left-0 opacity-100 transition-all group-data-[open=true]/sidebar-wrapper:md:opacity-0">
                  <SidebarTrigger>
                    <ForwardedIconComponent
                      name="PanelLeftOpen"
                      aria-hidden="true"
                      className=""
                    />
                  </SidebarTrigger>
                </div>
              </div>
              My Files
            </div>
            {files && files.length !== 0 ? (
              <div className="flex justify-between">
                <div className="flex w-full xl:w-5/12">
                  <Input
                    icon="Search"
                    data-testid="search-store-input"
                    type="text"
                    placeholder={`Search files...`}
                    className="mr-2 w-full"
                    value={quickFilterText || ""}
                    onChange={(event) => {
                      setQuickFilterText(event.target.value);
                    }}
                  />
                </div>
                <div className="flex items-center gap-2">
                  {UploadButtonComponent}
                  {/* <ImportButtonComponent /> */}
                </div>
              </div>
            ) : (
              <></>
            )}

            <div className="flex h-full flex-col py-4">
              {!files || !Array.isArray(files) ? (
                <div className="flex h-full w-full items-center justify-center">
                  <Loading />
                </div>
              ) : files.length > 0 ? (
                <DragWrapComponent onFileDrop={onFileDrop}>
                  <TableComponent
                    rowHeight={45}
                    headerHeight={45}
                    cellSelection={false}
                    tableOptions={{
                      hide_options: true,
                    }}
                    editable={[
                      {
                        field: "name",
                        onUpdate: handleRename,
                        editableCell: true,
                      },
                    ]}
                    enableCellTextSelection={false}
                    columnDefs={colDefs}
                    rowData={files.sort((a, b) => {
                      return sortByDate(
                        a.updated_at ?? a.created_at,
                        b.updated_at ?? b.created_at,
                      );
                    })}
                    className="ag-no-border w-full"
                    pagination
                    ref={tableRef}
                    quickFilterText={quickFilterText}
                    gridOptions={{
                      enableCellTextSelection: true,
                      stopEditingWhenCellsLoseFocus: true,
                      ensureDomOrder: true,
                      colResizeDefault: "shift",
                    }}
                  />
                </DragWrapComponent>
              ) : (
                <CardsWrapComponent
                  onFileDrop={onFileDrop}
                  dragMessage="Drop files to upload"
                >
                  <div className="flex h-full w-full flex-col items-center justify-center gap-8 pb-8">
                    <div className="flex flex-col items-center gap-2">
                      <h3 className="text-2xl font-semibold">No files</h3>
                      <p className="text-lg text-secondary-foreground">
                        Upload files or import from your preferred cloud.
                      </p>
                    </div>
                    <div className="flex items-center gap-2">
                      {UploadButtonComponent}
                      {/* <ImportButtonComponent /> */}
                    </div>
                  </div>
                </CardsWrapComponent>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default FilesPage;
