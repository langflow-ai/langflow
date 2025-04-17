import ForwardedIconComponent from "@/components/common/genericIconComponent";
import TableComponent, {
  TableComponentProps,
} from "@/components/core/parameterRenderComponent/components/tableComponent";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Sidebar,
  SidebarContent,
  SidebarGroup,
  SidebarGroupContent,
  SidebarHeader,
  SidebarMenu,
  SidebarProvider,
  useSidebar,
} from "@/components/ui/sidebar";
import { Textarea } from "@/components/ui/textarea";
import { handleOnNewValueType } from "@/CustomNodes/hooks/use-handle-new-value";
import { TableOptionsTypeAPI } from "@/types/api";
import { ToolsModalProps } from "@/types/components";
import { parseString } from "@/utils/stringManipulation";
import { cn } from "@/utils/utils";
import { ColDef } from "ag-grid-community";
import { AgGridReact } from "ag-grid-react";
import { cloneDeep } from "lodash";
import {
  ForwardedRef,
  forwardRef,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";

export default function ToolsTable({
  rows,
  data,
  setData,
  isAction,
  open,
  handleOnNewValue,
}: {
  rows: any[];
  data: any[];
  setData: (data: any[]) => void;
  open: boolean;
  handleOnNewValue: handleOnNewValueType;
  isAction: boolean;
}) {
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedRows, setSelectedRows] = useState<any[] | null>(null);
  const agGrid = useRef<AgGridReact>(null);

  const [focusedRow, setFocusedRow] = useState<any | null>(null);
  const [sidebarName, setSidebarName] = useState<string>("");
  const [sidebarDescription, setSidebarDescription] = useState<string>("");

  const { setOpen: setSidebarOpen } = useSidebar();

  useEffect(() => {
    const initialData = cloneDeep(rows);
    setData(initialData);
    const filter = initialData.filter((row) => row.status === true);
    setSelectedRows(filter);
  }, [rows, open]);

  useEffect(() => {
    const initialData = cloneDeep(rows);
    const filter = initialData.filter((row) => row.status === true);
    if (agGrid.current) {
      agGrid.current?.api?.forEachNode((node) => {
        if (filter.some((row) => row.name === node.data.name)) {
          node.setSelected(true);
        } else {
          node.setSelected(false);
        }
      });
    }
  }, [agGrid.current]);

  useEffect(() => {
    if (!open && selectedRows) {
      handleOnNewValue({
        value: data.map((row) =>
          selectedRows?.some((selected) => selected.name === row.name)
            ? { ...row, status: true }
            : { ...row, status: false },
        ),
      });
    }
  }, [open]);

  useEffect(() => {
    if (focusedRow) {
      setSidebarName(focusedRow.name);
      setSidebarDescription(focusedRow.description);
    } else {
      setSidebarName("");
      setSidebarDescription("");
    }
  }, [focusedRow]);

  const columnDefs: ColDef[] = [
    {
      field: "name",
      headerName: isAction ? "Flow" : "Name",
      flex: 1,
      valueGetter: (params) => params.data.name,
      valueParser: (params) =>
        parseString(params.newValue, ["snake_case", "no_blank"]),
    },
    {
      field: "tags",
      headerName: isAction ? "Action" : "Slug",
      flex: 2,
      resizable: false,
      valueGetter: (params) => params.data.tags.join(", "),
      cellClass: "text-muted-foreground",
    },
    {
      field: "tags",
      headerName: "Tags",
      flex: 1,
      hide: true,
    },
  ];
  const handleSelectionChanged = (event) => {
    if (open) {
      const selectedData = event.api.getSelectedRows();
      setSelectedRows(selectedData);
    }
  };

  const handleSidebarInputChange = (
    field: "name" | "description",
    value: string,
  ) => {
    if (!focusedRow) return;

    const updatedData = data.map((row) => {
      if (row.name === focusedRow.name) {
        return { ...row, [field]: value };
      }
      return row;
    });

    setData(updatedData);
    setFocusedRow((prev) => (prev ? { ...prev, [field]: value } : null));
  };

  return (
    <>
      <main className="flex h-full w-full flex-1 flex-col gap-2 overflow-hidden py-4">
        <div className="flex-none px-4">
          <Input
            icon="Search"
            placeholder="Search actions..."
            inputClassName="h-8"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
          />
        </div>
        <div className="flex-1 overflow-auto">
          <TableComponent
            columnDefs={columnDefs}
            rowData={data}
            quickFilterText={searchQuery}
            stopEditingWhenCellsLoseFocus={true}
            editable={[
              {
                field: "name",
                editableCell: true,
                onUpdate: () => {},
              },
              {
                field: "description",
                editableCell: true,
                onUpdate: () => {},
              },
            ]}
            ref={agGrid}
            rowSelection="multiple"
            suppressRowClickSelection={true}
            className="ag-tool-mode h-full w-full overflow-visible"
            headerHeight={32}
            rowHeight={32}
            onSelectionChanged={handleSelectionChanged}
            tableOptions={{
              block_hide: true,
            }}
            onRowClicked={(event) => {
              setFocusedRow(event.data);
              setSidebarOpen(true);
            }}
          />
        </div>
      </main>
      <Sidebar
        side="right"
        className="flex h-full flex-col border-l border-border"
      >
        <SidebarHeader className="flex-none px-4 py-4">
          <div className="flex flex-col gap-2">
            <h3 className="text-sm font-semibold">
              {focusedRow?.display_name ?? focusedRow?.name}
            </h3>
            <p className="text-sm text-muted-foreground">
              {focusedRow?.display_description ?? focusedRow?.description}
            </p>
          </div>
        </SidebarHeader>
        <SidebarContent className="flex flex-1 flex-col gap-0 overflow-auto px-2">
          {focusedRow && (
            <div className="flex h-full flex-col gap-4">
              <SidebarGroup className="flex-1">
                <SidebarGroupContent className="h-full">
                  <div className="flex h-full flex-col gap-4">
                    <div className="flex flex-col gap-1.5">
                      <label
                        className="text-sm font-medium"
                        htmlFor="sidebar-name-input"
                      >
                        {isAction ? "Flow Name" : "Tool Name"}
                      </label>
                      <Input
                        id="sidebar-name-input"
                        value={sidebarName}
                        onChange={(e) => {
                          setSidebarName(e.target.value);
                          handleSidebarInputChange("name", e.target.value);
                        }}
                        placeholder="Edit name..."
                      />
                    </div>
                    <div className="flex flex-col gap-1.5">
                      <div className="flex items-center justify-between">
                        <label
                          className="text-sm font-medium"
                          htmlFor="sidebar-desc-input"
                        >
                          {isAction ? "Flow Description" : "Tool Description"}
                        </label>
                        <Button
                          unstyled
                          onClick={() => {
                            setSidebarDescription(
                              focusedRow.display_description,
                            );
                          }}
                          disabled={
                            sidebarDescription ===
                              focusedRow.display_description ||
                            !focusedRow.description
                          }
                          size="iconMd"
                          className="group/rotate-icon"
                        >
                          <ForwardedIconComponent
                            name="RotateCcw"
                            className={cn(
                              "icon-size",
                              sidebarDescription !==
                                focusedRow.display_description
                                ? "text-muted-foreground hover:text-primary"
                                : "text-input",
                            )}
                          />
                        </Button>
                      </div>

                      <Textarea
                        id="sidebar-desc-input"
                        value={sidebarDescription}
                        onChange={(e) => {
                          setSidebarDescription(e.target.value);
                          handleSidebarInputChange(
                            "description",
                            e.target.value,
                          );
                        }}
                        placeholder="Edit description..."
                        className="h-24"
                      />
                    </div>
                  </div>
                </SidebarGroupContent>
              </SidebarGroup>
            </div>
          )}
        </SidebarContent>
      </Sidebar>
    </>
  );
}
