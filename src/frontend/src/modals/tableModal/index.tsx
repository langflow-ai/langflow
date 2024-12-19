import ForwardedIconComponent from "@/components/common/genericIconComponent";
import TableComponent, {
  TableComponentProps,
} from "@/components/core/parameterRenderComponent/components/tableComponent";
import { Button } from "@/components/ui/button";
import { TableOptionsTypeAPI } from "@/types/api";
import { DialogClose } from "@radix-ui/react-dialog";
import { AgGridReact } from "ag-grid-react";
import { ElementRef, ForwardedRef, forwardRef } from "react";
import BaseModal from "../baseModal";

interface TableModalProps extends TableComponentProps {
  tableTitle: string;
  description: string;
  disabled?: boolean;
  children: React.ReactNode;
  tableOptions?: TableOptionsTypeAPI;
  hideColumns?: boolean | string[];
}

const TableModal = forwardRef<AgGridReact, TableModalProps>(
  (
    { tableTitle, description, children, disabled, ...props }: TableModalProps,
    ref: ForwardedRef<AgGridReact>,
  ) => {
    return (
      <BaseModal
        onEscapeKeyDown={(e) => {
          if (
            (
              ref as React.RefObject<AgGridReact>
            )?.current?.api.getEditingCells().length
          ) {
            e.preventDefault();
          }
        }}
        disable={disabled}
      >
        <BaseModal.Trigger asChild>{children}</BaseModal.Trigger>
        <BaseModal.Header description={description}>
          <span className="pr-2">{tableTitle}</span>
          <ForwardedIconComponent name="Table" className="mr-2 h-4 w-4" />
        </BaseModal.Header>
        <BaseModal.Content>
          <TableComponent
            className="h-full w-full"
            ref={ref}
            {...props}
          ></TableComponent>
        </BaseModal.Content>
      </BaseModal>
    );
  },
);

export default TableModal;
