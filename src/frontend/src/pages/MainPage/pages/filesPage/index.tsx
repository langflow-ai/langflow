import ForwardedIconComponent from "@/components/common/genericIconComponent";
import ShadTooltip from "@/components/common/shadTooltipComponent";
import CardsWrapComponent from "@/components/core/cardsWrapComponent";
import TableComponent from "@/components/core/parameterRenderComponent/components/tableComponent";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { SidebarTrigger } from "@/components/ui/sidebar";
import FilesContextMenuComponent from "@/modals/fileManagerModal/components/filesContextMenuComponent";
import ImportButtonComponent from "@/modals/fileManagerModal/components/importButtonComponent";
import { FILE_ICONS } from "@/utils/styleUtils";
import { ColDef } from "ag-grid-community";
import { AgGridReact } from "ag-grid-react";
import { useRef, useState } from "react";

export const FilesPage = () => {
  const tableRef = useRef<AgGridReact<any>>(null);
  const files = [
    {
      type: "json",
      name: "user_profile_data.json",
      size: "640 KB",
      added: "02/02/2025",
    },
    {
      type: "csv",
      name: "Q4_Reports.csv",
      size: "80 KB",
      added: "02/02/2025",
    },
    {
      type: "txt",
      name: "Highschool Speech.txt",
      size: "10 KB",
      added: "01/02/2025",
    },
    {
      type: "pdf",
      name: "logoconcepts.pdf",
      size: "1.2 MB",
      added: "31/01/2025",
    },
  ];

  const colDefs: ColDef[] = [
    {
      headerName: "Name",
      field: "name",
      flex: 2,
      editable: false,
      filter: "agTextColumnFilter",
      resizable: false,
      cellClass: "cursor-text select-text",
      cellRenderer: (params) => {
        return (
          <div className="flex items-center gap-2 font-medium">
            <ForwardedIconComponent
              name={FILE_ICONS[params.value.split(".")[1]]?.icon}
              className={FILE_ICONS[params.value.split(".")[1]]?.color}
            />
            {params.value}
          </div>
        );
      }, //This column will be twice as wide as the others
    }, //This column will be twice as wide as the others
    {
      headerName: "Type",
      field: "type",
      filter: "agTextColumnFilter",
      editable: false,
      resizable: false,
      valueFormatter: (params) => {
        return params.value.toUpperCase();
      },
      cellClass: "text-muted-foreground cursor-text select-text",
    },
    {
      headerName: "Size",
      field: "size",
      editable: false,
      resizable: false,
      cellClass: "text-muted-foreground cursor-text select-text",
    },
    {
      headerName: "Added",
      field: "added",
      editable: false,
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
            <FilesContextMenuComponent
              isLocal={true}
              handleSelectOptionsChange={() => {}}
            >
              <Button variant="ghost" size="iconMd">
                <ForwardedIconComponent name="EllipsisVertical" />
              </Button>
            </FilesContextMenuComponent>
          </div>
        );
      },
    },
  ];

  const [quickFilterText, setQuickFilterText] = useState("");
  return (
    <CardsWrapComponent
      onFileDrop={() => {}}
      dragMessage={`Drag your files here`}
    >
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
                Files
              </div>
              {
                <>
                  {/* Search and filters */}
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
                      <ShadTooltip content="Upload File" side="bottom">
                        <Button
                          variant="outline"
                          className="!px-3 md:!px-4 md:!pl-3.5"
                          onClick={() => {}}
                          id="new-project-btn"
                          data-testid="new-project-btn"
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
                      <ImportButtonComponent>
                        <Button className="font-semibold">
                          Import from
                          <ForwardedIconComponent
                            name="ChevronDown"
                            className="ml-2 h-4 w-4"
                          />
                        </Button>
                      </ImportButtonComponent>
                    </div>
                  </div>
                </>
              }
              <div className="flex h-full flex-col py-4">
                <TableComponent
                  rowHeight={45}
                  headerHeight={45}
                  cellSelection={false}
                  tableOptions={{
                    hide_options: true,
                  }}
                  enableCellTextSelection={false}
                  columnDefs={colDefs}
                  rowData={files}
                  className="ag-no-border w-full"
                  pagination
                  ref={tableRef}
                  quickFilterText={quickFilterText}
                  gridOptions={{
                    suppressCellFocus: true,
                    enableCellTextSelection: true,
                    ensureDomOrder: true,
                  }}
                />
              </div>
            </div>
          </div>
        </div>
      </div>
    </CardsWrapComponent>
  );
};

export default FilesPage;
