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

  const getRowId = useMemo(() => {
    return (params: any) => params.data.display_name ?? params.data.name;
  }, []);

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
        if (
          filter.some(
            (row) =>
              (row.display_name ?? row.name) ===
              (node.data.display_name ?? node.data.name),
          )
        ) {
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
        value: data.map((row) => {
          const processedValue = (
            row.name !== ""
              ? parseString(row.name, ["snake_case", "no_blank", "lowercase"])
              : parseString(row.display_name, [
                  "snake_case",
                  "no_blank",
                  "lowercase",
                ])
          ).slice(0, 46);

          const processedDescription =
            row.description !== "" ? row.description : row.display_description;

          return selectedRows?.some(
            (selected) =>
              (selected.display_name ?? selected.name) ===
              (row.display_name ?? row.name),
          )
            ? {
                ...row,
                status: true,
                name: processedValue,
                description: processedDescription,
              }
            : {
                ...row,
                status: false,
                name: processedValue,
                description: processedDescription,
              };
        }),
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
      field: isAction ? "display_name" : "name",
      headerName: isAction ? "Flow Name" : "Name",
      flex: 1,
      valueGetter: (params) =>
        !isAction
          ? params.data.name !== ""
            ? parseString(params.data.name, [
                "snake_case",
                "no_blank",
                "lowercase",
              ])
            : parseString(params.data.display_name, [
                "snake_case",
                "no_blank",
                "lowercase",
              ])
          : params.data.display_name,
    },
    {
      field: "description",
      headerName: "Description",
      flex: 2,
      resizable: false,
      cellClass: "text-muted-foreground",
    },
    {
      field: isAction ? "name" : "tags",
      headerName: isAction ? "Action" : "Slug",
      flex: 1,
      resizable: false,
      valueGetter: (params) =>
        isAction
          ? params.data.name !== ""
            ? parseString(params.data.name, [
                "snake_case",
                "no_blank",
                "uppercase",
              ])
            : parseString(params.data.display_name, [
                "snake_case",
                "no_blank",
                "uppercase",
              ])
          : params.data.tags.join(", "),
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

    const originalName = focusedRow.display_name;

    setFocusedRow((prev) => (prev ? { ...prev, [field]: value } : null));

    if (agGrid.current) {
      const updatedRow = { ...focusedRow, [field]: value };

      agGrid.current.api.applyTransaction({
        update: [updatedRow],
      });

      const updatedData = data.map((row) =>
        (row.display_name ?? row.name) === originalName ? updatedRow : row,
      );
      setData(updatedData);
    }
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
            getRowId={getRowId}
          />
        </div>
      </main>
      <Sidebar
        side="right"
        className="flex h-full flex-col border-l border-border"
      >
        <SidebarHeader className="flex-none px-4 py-4">
          <div className="flex flex-col gap-2" data-testid="sidebar_header">
            <h3
              className="text-sm font-semibold"
              data-testid="sidebar_header_name"
            >
              {focusedRow?.display_name ?? focusedRow?.name}
            </h3>
            <p
              className="text-sm text-muted-foreground"
              data-testid="sidebar_header_description"
            >
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
                    <div className="flex flex-col gap-2">
                      <label
                        className="text-sm font-medium"
                        htmlFor="sidebar-name-input"
                      >
                        {isAction ? "Action Name" : "Tool Name"}
                      </label>

                      <Input
                        id="sidebar-name-input"
                        value={sidebarName}
                        onChange={(e) => {
                          setSidebarName(e.target.value);
                          handleSidebarInputChange("name", e.target.value);
                        }}
                        maxLength={46}
                        placeholder="Edit name..."
                        data-testid="input_update_name"
                      />
                      <div className="text-xs text-muted-foreground">
                        {isAction
                          ? "Used as the function name when this flow is exposed to clients. Keep it short and descriptive."
                          : "Used as the function name when this tool is exposed to the agent. Keep it short and descriptive."}
                      </div>
                    </div>
                    <div className="flex flex-col gap-2">
                      <label
                        className="text-sm font-medium"
                        htmlFor="sidebar-desc-input"
                      >
                        {isAction ? "Action Description" : "Tool Description"}
                      </label>

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
                        data-testid="input_update_description"
                      />
                      <div className="text-xs text-muted-foreground">
                        {isAction
                          ? "This is the description for the action exposed to the clients. Optimize for clarity and relevance to end users."
                          : "This is the description for the tool exposed to the agents. Optimize for clarity and relevance to end users."}
                      </div>
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
