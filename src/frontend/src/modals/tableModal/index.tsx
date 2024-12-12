import ForwardedIconComponent from "@/components/common/genericIconComponent";
import TableComponent, {
  TableComponentProps,
} from "@/components/core/parameterRenderComponent/components/tableComponent";
import { Button } from "@/components/ui/button";
import { DialogClose } from "@radix-ui/react-dialog";
import { ElementRef, forwardRef, useState } from "react";
import BaseModal from "../baseModal";

interface TableModalProps extends TableComponentProps {
  tableTitle: string;
  description: string;
  disabled?: boolean;
  children: React.ReactNode;
}

const TableModal = forwardRef<
  ElementRef<typeof TableComponent>,
  TableModalProps
>(
  (
    { tableTitle, description, children, disabled, ...props }: TableModalProps,
    ref,
  ) => {
    return (
      <BaseModal disable={disabled}>
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
