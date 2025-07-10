import type { ColDef } from "ag-grid-community";
import type { AgGridReact } from "ag-grid-react";
import { useEffect, useRef, useState } from "react";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import TableComponent from "@/components/core/parameterRenderComponent/components/tableComponent";
import { Checkbox } from "@/components/ui/checkbox";
import useDuplicateFlows from "@/pages/MainPage/hooks/use-handle-duplicate";
import useFlowStore from "@/stores/flowStore";
import type { ComponentsToUpdateType } from "@/types/zustand/flow";
import { cn } from "@/utils/utils";
import BaseModal from "../baseModal";

export default function UpdateComponentModal({
  open,
  setOpen,
  onUpdateNode,
  children,
  components,
  isMultiple = false,
}: {
  open: boolean;
  setOpen: (open: boolean) => void;
  onUpdateNode: (updatedComponents?: string[]) => void;
  children?: React.ReactNode;
  components: ComponentsToUpdateType[];
  isMultiple?: boolean;
}) {
  const [backupFlow, setBackupFlow] = useState<boolean>(true);
  const [loading, setLoading] = useState<boolean>(false);
  const [selectedComponents, setSelectedComponents] = useState<Set<string>>(
    new Set(components.filter((c) => !c.breakingChange).map((c) => c.id)),
  );
  const agGrid = useRef<AgGridReact>(null);
  const currentFlow = useFlowStore((state) => state.currentFlow);

  const { handleDuplicate } = useDuplicateFlows({
    flow: currentFlow
      ? { ...currentFlow, name: currentFlow.name + " (Backup)" }
      : undefined,
  });

  const handleUpdate = () => {
    setLoading(true);
    if (backupFlow) {
      handleDuplicate().then(() => {
        onUpdateNode(
          components.length > 0 ? Array.from(selectedComponents) : undefined,
        );
        setLoading(false);
        setOpen(false);
      });
    } else {
      onUpdateNode(
        components.length > 0 ? Array.from(selectedComponents) : undefined,
      );
      setLoading(false);
      setOpen(false);
    }
  };

  const columnDefs: ColDef[] = [
    { field: "id", hide: true },
    {
      headerName: "Component",
      field: "display_name",
      headerClass: "!text-mmd !font-normal",
      flex: 1,
      headerCheckboxSelection: true,
      checkboxSelection: true,
      resizable: false,
      cellRenderer: (params) => {
        return (
          <div className="flex items-center gap-3">
            {params.data.icon && (
              <ForwardedIconComponent
                name={params.data.icon}
                className="h-4 w-4"
              />
            )}
            {params.value}
          </div>
        );
      },
    },
    {
      headerName: "Update Type",
      field: "breakingChange",
      headerClass: "!text-mmd !font-normal",
      resizable: false,
      flex: 1,
      cellClass: "text-muted-foreground",
      cellRenderer: (params) => {
        return params.value ? (
          <span className="font-semibold text-accent-amber-foreground">
            Breaking
          </span>
        ) : (
          <span>Standard</span>
        );
      },
    },
  ];

  useEffect(() => {
    if (open) {
      setBackupFlow(true);
      setSelectedComponents(
        new Set(components.filter((c) => !c.breakingChange).map((c) => c.id)),
      );
    }
  }, [open]);

  useEffect(() => {
    if (agGrid.current) {
      agGrid.current?.api?.forEachNode((node) => {
        if (selectedComponents.has(node.data.id)) {
          node.setSelected(true);
        } else {
          node.setSelected(false);
        }
      });
    }
  }, [agGrid.current, selectedComponents, open]);

  return (
    <BaseModal
      closeButtonClassName="!top-2 !right-3"
      open={open}
      setOpen={setOpen}
      size="small-update"
      className="px-4 py-3"
    >
      <BaseModal.Trigger asChild>{children ?? <></>}</BaseModal.Trigger>
      <BaseModal.Header>
        <span className="">
          Update{" "}
          {isMultiple ? "components" : (components?.[0]?.display_name ?? "")}
        </span>
      </BaseModal.Header>
      <BaseModal.Content overflowHidden>
        <div className="flex flex-col gap-6">
          <div className="flex flex-col gap-3 text-sm text-muted-foreground">
            {isMultiple ? (
              <p>
                Updates marked as{" "}
                <span className="font-semibold text-accent-amber-foreground">
                  breaking
                </span>{" "}
                may change inputs, outputs, or component behavior. In some
                cases, they will disconnect components from your flow, requiring
                you to review or reconnect them afterward. Components added from
                the sidebar always use the latest version.
              </p>
            ) : (
              <>
                <p>
                  This update may change inputs, outputs, or component behavior.
                  In some cases, it will{" "}
                  <span className="font-semibold text-accent-amber-foreground">
                    disconnect this component from your flow
                  </span>
                  , requiring you to review or reconnect it afterward.
                </p>
                <p>
                  Components added from the sidebar always use the latest
                  version.
                </p>
              </>
            )}
          </div>
          {isMultiple && (
            <div className="-mx-4">
              <TableComponent
                columnDefs={columnDefs}
                ref={agGrid}
                domLayout="autoHeight"
                rowData={components}
                rowSelection="multiple"
                className="ag-tool-mode ag-no-selection"
                rowHeight={30}
                headerHeight={30}
                suppressRowClickSelection={false}
                onSelectionChanged={(event) => {
                  const selectedIds = event.api
                    .getSelectedRows()
                    .map((row) => row.id);
                  setSelectedComponents(new Set(selectedIds));
                }}
                suppressRowHoverHighlight={true}
                tableOptions={{ hide_options: true }}
              />
            </div>
          )}
          <div
            className={cn(
              "mb-3 flex items-center gap-3 rounded-md border p-3 text-sm transition-all",
              !backupFlow && "border-accent-amber-foreground bg-accent-amber",
            )}
          >
            <Checkbox
              checked={backupFlow}
              onCheckedChange={(checked) =>
                setBackupFlow(checked === "indeterminate" ? false : checked)
              }
              className="bg-muted"
              id="backupFlow"
              data-testid="backup-flow-checkbox"
            />
            <label htmlFor="backupFlow" className="cursor-pointer select-none">
              Create backup flow before updating
            </label>
          </div>
        </div>
      </BaseModal.Content>
      <BaseModal.Footer
        submit={{
          label: "Update Component" + (components.length > 1 ? "s" : ""),
          onClick: handleUpdate,
          disabled: isMultiple && selectedComponents.size === 0,
          loading,
        }}
      ></BaseModal.Footer>
    </BaseModal>
  );
}
