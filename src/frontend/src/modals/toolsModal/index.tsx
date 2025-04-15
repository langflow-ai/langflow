import ForwardedIconComponent from "@/components/common/genericIconComponent";
import TableComponent, {
  TableComponentProps,
} from "@/components/core/parameterRenderComponent/components/tableComponent";
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
        setOpen={(newOpen) => {
          handleSetOpen(newOpen);
        }}
      >
        <BaseModal.Header>
          <ForwardedIconComponent
            name={icon ?? "Table"}
            className="mr-2 h-6 w-6"
          />
          <span className="">{title}</span>
        </BaseModal.Header>
        <BaseModal.Content>..</BaseModal.Content>
      </BaseModal>
    );
  },
);

export default ToolsModal;
