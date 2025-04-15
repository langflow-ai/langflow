import ForwardedIconComponent from "@/components/common/genericIconComponent";
import TableComponent, {
  TableComponentProps,
} from "@/components/core/parameterRenderComponent/components/tableComponent";
import ComboBoxItem from "@/CustomNodes/GenericNode/components/ListSelectionComponent/ComboBoxItem";
import { handleOnNewValueType } from "@/CustomNodes/hooks/use-handle-new-value";
import { TableOptionsTypeAPI } from "@/types/api";
import { AgGridReact } from "ag-grid-react";
import { ForwardedRef, forwardRef } from "react";
import BaseModal from "../baseModal";

interface ToolsModalProps {
  open: boolean;
  setOpen: (open: boolean) => void;
  description: string;
  rows: {
    name: string;
    tags: string[];
    description: string;
  }[];
  handleOnNewValue: handleOnNewValueType;
  title: string;
  icon: string;
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

    return (
      <BaseModal
        open={open}
        className="gap-0 p-0"
        setOpen={(newOpen) => {
          handleSetOpen(newOpen);
        }}
      >
        <BaseModal.Header>
          <div className="flex w-full flex-row items-center border-b border-border px-4 py-3">
            <div className="mr-2 rounded-md border border-border bg-primary">
              <ForwardedIconComponent
                name={icon ?? "Table"}
                className="h-6 w-6 p-1.5"
              />
            </div>
            <div className="text-[13px]">{title}</div>
          </div>
        </BaseModal.Header>
        <BaseModal.Content className="px-4 py-3">
          <div className="flex flex-col gap-2">
            {rows.map((item) => (
              <ComboBoxItem key={item.name} item={item} />
            ))}
          </div>
        </BaseModal.Content>
      </BaseModal>
    );
  },
);

export default ToolsModal;
