import ForwardedIconComponent from "@/components/common/genericIconComponent";
import ShadTooltip from "@/components/common/shadTooltipComponent";
import TableComponent from "@/components/core/parameterRenderComponent/components/tableComponent";
import { Input } from "@/components/ui/input";
import { Separator } from "@/components/ui/separator";
import {
  Sidebar,
  SidebarContent,
  SidebarGroup,
  SidebarGroupContent,
  SidebarHeader,
  useSidebar,
} from "@/components/ui/sidebar";
import { Textarea } from "@/components/ui/textarea";
import { handleOnNewValueType } from "@/CustomNodes/hooks/use-handle-new-value";
import { APITemplateType } from "@/types/api";
import { parseString } from "@/utils/stringManipulation";
import { ColDef } from "ag-grid-community";
import { AgGridReact } from "ag-grid-react";
import { cloneDeep } from "lodash";
import { useEffect, useMemo, useRef, useState } from "react";

export default function ToolsTable({
  rows,
  data,
  setData,
  isAction,
  placeholder,
  open,
  handleOnNewValue,
}: {
  rows: any[];
  data: any[];
  setData: (data: any[]) => void;
  open: boolean;
  handleOnNewValue: handleOnNewValueType;
  isAction: boolean;
  placeholder: string;
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
    if (!open || placeholder.startsWith("Loading")) {
      handleOnNewValue({
        value: data.map((row) => {
          const name = parseString(row.name, [
            "snake_case",
            "no_blank",
            "lowercase",
          ]);
          const display_name = parseString(row.display_name, [
            "snake_case",
            "no_blank",
            "lowercase",
          ]);
          const processedValue = (
            name !== "" && name !== display_name
              ? name
              : isAction
                ? ""
                : display_name
          ).slice(0, 46);

          const processedDescription =
            row.description !== "" &&
            row.description !== row.display_description
              ? row.description
              : isAction
                ? ""
                : row.display_description;

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
  }, [open, placeholder]);

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
          ? parseString(
              params.data.display_name !== ""
                ? params.data.display_name
                : params.data.name,
              ["space_case"],
            )
          : params.data.display_name,
    },
    {
      field: "description",
      headerName: "Description",
      flex: 2,
      cellClass: "text-muted-foreground",
    },
    {
      field: "name",
      headerName: isAction ? "Action" : "Slug",
      flex: 1,
      resizable: false,
      valueGetter: (params) =>
        params.data.name !== ""
          ? parseString(params.data.name, [
              "snake_case",
              "no_blank",
              "uppercase",
            ])
          : isAction
            ? parseString(params.data.display_name, [
                "snake_case",
                "no_blank",
                "uppercase",
              ])
            : parseString(params.data.tags.join(", "), [
                "snake_case",
                "uppercase",
              ]),
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

  const actionArgs = useMemo(() => {
    return Object.entries(focusedRow?.args ?? {}).map(
      ([key, value]: [string, any]) => ({
        display_name: value.title,
        name: key,
        description: value.description ?? null,
      }),
    );
  }, [focusedRow]);

  const handleDescriptionChange = (e) => {
    setSidebarDescription(e.target.value);
    handleSidebarInputChange("description", e.target.value);
  };

  const handleNameChange = (e) => {
    setSidebarName(e.target.value);
    handleSidebarInputChange("name", e.target.value);
  };

  const handleSearchChange = (e) => setSearchQuery(e.target.value);

  const tableOptions = {
    block_hide: true,
  };

  const handleRowClicked = (event) => {
    setFocusedRow(event.data);
    setSidebarOpen(true);
  };

  const rowName = useMemo(() => {
    return parseString(focusedRow?.display_name || focusedRow?.name || "", [
      "space_case",
    ]);
  }, [focusedRow]);

  return (
    <>
      <main className="flex h-full w-full flex-1 flex-col gap-2 overflow-hidden py-4">
        <div className="flex-none px-4">
          <Input
            icon="Search"
            placeholder="Search actions..."
            inputClassName="h-8"
            value={searchQuery}
            onChange={handleSearchChange}
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
            tableOptions={tableOptions}
            onRowClicked={handleRowClicked}
            getRowId={getRowId}
          />
        </div>
      </main>
      <Sidebar
        side="right"
        className="flex h-full flex-col overflow-auto border-l border-border"
      >
        <SidebarHeader className="flex-none px-4 py-4">
          {focusedRow &&
            (isAction || !focusedRow.readonly ? (
              <div className="flex flex-col gap-4">
                <div className="flex flex-col gap-2">
                  <label
                    className="text-mmd font-medium"
                    htmlFor="sidebar-name-input"
                  >
                    Name
                  </label>

                  <Input
                    id="sidebar-name-input"
                    value={sidebarName}
                    onChange={handleNameChange}
                    maxLength={46}
                    placeholder="Edit name..."
                    data-testid="input_update_name"
                  />
                  <div className="text-xs text-muted-foreground">
                    {isAction
                      ? "Used as the function name when this flow is exposed to clients."
                      : "Used as the function name when this tool is exposed to the agent."}
                  </div>
                </div>
                <div className="flex flex-col gap-2">
                  <label
                    className="text-mmd font-medium"
                    htmlFor="sidebar-desc-input"
                  >
                    Description
                  </label>

                  <Textarea
                    id="sidebar-desc-input"
                    value={sidebarDescription}
                    onChange={handleDescriptionChange}
                    placeholder="Edit description..."
                    className="h-24"
                    data-testid="input_update_description"
                  />
                  <div className="text-xs text-muted-foreground">
                    {isAction
                      ? "This is the description for the action exposed to the clients."
                      : "This is the description for the tool exposed to the agents."}
                  </div>
                </div>
              </div>
            ) : (
              <div className="flex flex-col gap-1" data-testid="sidebar_header">
                <h3
                  className="text-base font-medium"
                  data-testid="sidebar_header_name"
                >
                  {rowName}
                </h3>
                <p
                  className="text-mmd text-muted-foreground"
                  data-testid="sidebar_header_description"
                >
                  {focusedRow?.display_description ?? focusedRow?.description}
                </p>
              </div>
            ))}
        </SidebarHeader>
        {!isAction && <Separator />}
        <SidebarContent className="flex flex-1 flex-col gap-0 overflow-visible px-2">
          {focusedRow && (
            <div className="flex h-full flex-col gap-4">
              <SidebarGroup className="flex-1">
                <SidebarGroupContent className="h-full pb-4">
                  <div className="flex h-full flex-col gap-4">
                    {actionArgs.length > 0 && (
                      <div className="flex flex-col gap-1.5">
                        <h3 className="mt-2 text-base font-medium">
                          Parameters
                        </h3>
                        <p className="text-mmd text-muted-foreground">
                          Manage inputs for this action
                        </p>
                      </div>
                    )}
                    {actionArgs.map((field, index) => (
                      <div key={index} className="flex flex-col gap-2">
                        <label className="flex text-sm font-medium">
                          {field.display_name}
                          {field.description && (
                            <ShadTooltip content={field.description}>
                              <div className="flex items-center text-sm font-medium hover:cursor-help">
                                <ForwardedIconComponent
                                  name="info"
                                  className="ml-1.5 h-4 w-4 text-muted-foreground"
                                  aria-hidden="true"
                                />
                              </div>
                            </ShadTooltip>
                          )}
                        </label>
                        <Input
                          id="sidebar-desc-input"
                          disabled
                          placeholder="Input controlled by the agent"
                          onChange={(e) => {}}
                        />
                      </div>
                    ))}
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
