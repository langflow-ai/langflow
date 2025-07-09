import ForwardedIconComponent from "@/components/common/genericIconComponent";
import TableComponent, {
  type TableComponentProps,
} from "@/components/core/parameterRenderComponent/components/tableComponent";
import type { TableOptionsTypeAPI } from "@/types/api";
import type { AgGridReact } from "ag-grid-react";
import { type ForwardedRef, forwardRef } from "react";
import BaseModal from "../baseModal";

interface TableModalProps extends TableComponentProps {
  tableTitle: string;
  description: string;
  disabled?: boolean;
  children: React.ReactNode;
  tableOptions?: TableOptionsTypeAPI;
  hideColumns?: boolean | string[];
  tableIcon?: string;
  open?: boolean;
  setOpen?: (open: boolean) => void;
  onSave?: () => void;
  onCancel?: () => void;
}

const TableModal = forwardRef<AgGridReact, TableModalProps>(
  (
    {
      tableTitle,
      description,
      children,
      disabled,
      tableIcon,
      open,
      setOpen,
      onSave,
      onCancel,
      ...props
    }: TableModalProps,
    ref: ForwardedRef<AgGridReact>,
  ) => {
    const handleSetOpen = (newOpen: boolean) => {
      if (!newOpen && onCancel) {
        onCancel();
      }
      if (setOpen) {
        setOpen(newOpen);
      }
    };

    const handleOnEscapeKeyDown = (e: KeyboardEvent) => {
      const editingCells = (
        ref as React.RefObject<AgGridReact>
      )?.current?.api?.getEditingCells();

      if (editingCells && editingCells.length > 0) {
        e.preventDefault();
      }
    };

    return (
      <BaseModal
        onEscapeKeyDown={(e) => {
          handleOnEscapeKeyDown(e);
        }}
        disable={disabled}
        open={open}
        setOpen={(newOpen) => {
          handleSetOpen(newOpen);
        }}
      >
        <BaseModal.Trigger asChild>{children}</BaseModal.Trigger>
        <BaseModal.Header
          description={props.tableOptions?.description ?? description}
        >
          <span className="pr-2">{tableTitle}</span>
          <ForwardedIconComponent
            name={tableIcon ?? "Table"}
            className="mr-2 h-4 w-4"
          />
        </BaseModal.Header>
        <BaseModal.Content>
          <TableComponent
            className="h-full w-full"
            ref={ref}
            {...props}
          ></TableComponent>
        </BaseModal.Content>
        <BaseModal.Footer
          submit={onSave ? { label: "Save", onClick: onSave } : undefined}
        ></BaseModal.Footer>
      </BaseModal>
    );
  },
);

export default TableModal;
