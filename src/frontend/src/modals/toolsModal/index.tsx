import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { SidebarProvider } from "@/components/ui/sidebar";
import { handleOnNewValueType } from "@/CustomNodes/hooks/use-handle-new-value";
import { APITemplateType } from "@/types/api";
import { AgGridReact } from "ag-grid-react";
import { cloneDeep } from "lodash";
import { ForwardedRef, forwardRef, useState } from "react";
import BaseModal from "../baseModal";
import ToolsTable from "./components/toolsTable";

interface ToolsModalProps {
  open: boolean;
  setOpen: (open: boolean) => void;
  description: string;
  rows: {
    name: string;
    tags: string[];
    description: string;
    status: boolean;
  }[];
  handleOnNewValue: handleOnNewValueType;
  title: string;
  icon?: string;
  isAction?: boolean;
}

const ToolsModal = forwardRef<AgGridReact, ToolsModalProps>(
  (
    {
      description,
      rows,
      handleOnNewValue,
      title,
      icon,
      open,
      isAction = false,
      setOpen,
      ...props
    }: ToolsModalProps,
    ref: ForwardedRef<AgGridReact>,
  ) => {
    const handleSetOpen = (newOpen: boolean) => {
      if (setOpen) {
        setOpen(newOpen);
      }
    };

    const [data, setData] = useState<any[]>(cloneDeep(rows));

    return (
      <BaseModal
        open={open}
        size="templates"
        className="flex max-h-[50vh] gap-0 p-0"
        setOpen={(newOpen) => {
          handleSetOpen(newOpen);
        }}
      >
        <BaseModal.Header>
          <div className="flex w-full flex-row items-center border-b border-border px-4 py-3">
            {icon && (
              <ForwardedIconComponent name={icon} className="mr-2 h-6 w-6" />
            )}
            <div>{title}</div>
          </div>
        </BaseModal.Header>
        <BaseModal.Content overflowHidden className="flex flex-col p-0">
          <div className="flex h-full">
            <SidebarProvider width="20rem" defaultOpen={false}>
              <ToolsTable
                rows={rows}
                isAction={isAction}
                data={data}
                setData={setData}
                open={open}
                handleOnNewValue={handleOnNewValue}
              />
            </SidebarProvider>
          </div>
        </BaseModal.Content>
      </BaseModal>
    );
  },
);

export default ToolsModal;
