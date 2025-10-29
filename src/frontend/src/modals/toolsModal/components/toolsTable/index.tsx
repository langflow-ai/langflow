import type { ColDef } from "ag-grid-community";
import type { AgGridReact } from "ag-grid-react";
import { cloneDeep } from "lodash";
import { useEffect, useMemo, useRef, useState } from "react";
import type { handleOnNewValueType } from "@/CustomNodes/hooks/use-handle-new-value";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import ShadTooltip from "@/components/common/shadTooltipComponent";
import TableComponent from "@/components/core/parameterRenderComponent/components/tableComponent";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Separator } from "@/components/ui/separator";
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupContent,
  useSidebar,
} from "@/components/ui/sidebar";
import { Textarea } from "@/components/ui/textarea";
import { parseString, sanitizeMcpName } from "@/utils/stringManipulation";

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

  const editedSelection = useRef<boolean>(false);
  const applyingSelection = useRef<boolean>(false);
  const previousRowsCount = useRef<number>(0);
  const skipSelectionReapply = useRef<number>(0);

  const { setOpen: setSidebarOpen } = useSidebar();

  const getRowId = useMemo(() => {
    return (params: any) =>
      params.data._uniqueId ||
      `${params.data.name}_${params.data.display_name}`;
  }, []);

  useEffect(() => {
    if (!open) return;
    previousRowsCount.current = rows.length;
    const initialData = cloneDeep(rows).map((row, index) => ({
      ...row,
      _uniqueId: `${row.name}_${row.display_name}_${index}`,
    }));
    setData(initialData);
    const filter = initialData.filter((row) => row.status === true);
    setSelectedRows(filter);
    editedSelection.current = false;
  }, [open]);

  useEffect(() => {
    if (!open || !selectedRows) return;
    if (previousRowsCount.current === rows.length) return;

    previousRowsCount.current = rows.length;
    const updatedData = cloneDeep(rows).map((row, index) => ({
      ...row,
      _uniqueId: `${row.name}_${row.display_name}_${index}`,
    }));

    // Increment skip counter to prevent re-applying selection
    skipSelectionReapply.current++;

    setData(updatedData);

    const updatedSelection = updatedData.filter((row) =>
      selectedRows.some((selected) => selected.name === row.name),
    );
    setSelectedRows(updatedSelection);
  }, [rows]);

  useEffect(() => {
    if (!agGrid.current?.api || !selectedRows || !open) return;

    // Don't re-apply selection if we're just editing data fields (slug/description)
    if (skipSelectionReapply.current > 0) {
      skipSelectionReapply.current--;
      return;
    }

    applyingSelection.current = true;
    agGrid.current.api.setGridOption("suppressRowClickSelection", true);

    const selectedIds = new Set(selectedRows.map((row) => row.name));
    agGrid.current.api.forEachNode((node) => {
      const shouldSelect = selectedIds.has(node.data.name);
      if (node.isSelected() !== shouldSelect) {
        node.setSelected(shouldSelect, false);
      }
    });

    agGrid.current.api.setGridOption("suppressRowClickSelection", false);
    setTimeout(() => {
      applyingSelection.current = false;
    }, 50);
  }, [selectedRows, open]);

  useEffect(() => {
    if (!open) {
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
                ? sanitizeMcpName(display_name || row.name, 46)
                : display_name
          ).slice(0, 46);

          const processedDescription =
            row.description !== "" &&
            row.description !== row.display_description
              ? row.description
              : isAction
                ? ""
                : row.display_description;

          return selectedRows?.some((selected) => selected.name === row.name)
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
      headerName: isAction ? "Tool" : "Slug",
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
            ? sanitizeMcpName(params.data.display_name, 46).toUpperCase()
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
    if (!open || applyingSelection.current) return;

    const selectedData = event.api.getSelectedRows();
    editedSelection.current = true;
    setSelectedRows(selectedData);
  };

  const handleSidebarInputChange = (
    field: "name" | "description",
    value: string,
  ) => {
    if (!focusedRow) return;

    const originalUniqueId = focusedRow._uniqueId;
    const updatedRow = {
      ...focusedRow,
      [field]: value,
      _uniqueId: originalUniqueId,
    };

    setFocusedRow(updatedRow);

    if (agGrid.current && originalUniqueId) {
      // Increment skip counter to prevent re-applying selection
      skipSelectionReapply.current++;

      // Update only via applyTransaction
      agGrid.current.api.applyTransaction({
        update: [updatedRow],
      });

      const updatedData = data.map((row) =>
        row._uniqueId === originalUniqueId ? updatedRow : row,
      );
      setData(updatedData);

      // Update selectedRows to reflect the updated data
      setSelectedRows(
        (prevSelected) =>
          prevSelected?.map((row) =>
            row._uniqueId === originalUniqueId ? updatedRow : row,
          ) || null,
      );
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
    const rawValue = e.target.value;
    const sanitizedValue = isAction ? sanitizeMcpName(rawValue, 46) : rawValue;
    setSidebarName(sanitizedValue);
    handleSidebarInputChange("name", sanitizedValue);
  };

  const handleSearchChange = (e) => setSearchQuery(e.target.value);

  const tableOptions = {
    block_hide: true,
    hide_options: false,
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

  const handleClose = () => {
    setSidebarOpen(false);
  };

  return (
    <>
      <main className="flex h-full w-full flex-1 flex-col gap-2 overflow-hidden py-4">
        <div className="flex-none px-4">
          <Input
            icon="Search"
            placeholder="Search tools..."
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
            pagination={true}
            paginationPageSize={50}
          />
        </div>
      </main>
      <Sidebar
        side="right"
        className="flex h-full flex-col overflow-auto border-l border-border"
      >
        <SidebarContent className="flex flex-1 flex-col gap-2 overflow-y-auto p-0">
          {focusedRow &&
            (isAction || !focusedRow.readonly ? (
              <div className="flex flex-col gap-4 p-4">
                <div className="flex flex-col gap-2">
                  <label
                    className="text-mmd font-medium"
                    htmlFor="sidebar-name-input"
                  >
                    {isAction ? "Tool name" : "Slug"}
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
                    {isAction ? "Tool description" : "Description"}
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
                      ? "This is the description for the tool exposed to a client."
                      : "This is the description for the tool exposed to the agents."}
                  </div>
                </div>
              </div>
            ) : (
              <div
                className="flex flex-col gap-1 p-4"
                data-testid="sidebar_header"
              >
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
          {!isAction && actionArgs.length > 0 && <Separator />}
          {focusedRow && (
            <div className="flex h-full flex-col gap-4 p-2">
              <SidebarGroup className="flex-1">
                <SidebarGroupContent className="h-full">
                  <div className="flex h-full flex-col gap-4">
                    {actionArgs.length > 0 && (
                      <div className="flex flex-col gap-1.5">
                        <h3 className="text-base font-medium">Parameters</h3>
                        <p className="text-mmd text-muted-foreground">
                          Manage inputs for this tool
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
        <SidebarFooter>
          <div className="flex justify-end w-full p-2">
            <Button
              variant="primary"
              size="sm"
              onClick={handleClose}
              data-testid="btn_close_tools_modal"
            >
              Close
            </Button>
          </div>
        </SidebarFooter>
      </Sidebar>
    </>
  );
}
