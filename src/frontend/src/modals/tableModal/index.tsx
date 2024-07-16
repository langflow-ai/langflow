import ForwardedIconComponent from "@/components/genericIconComponent";
import TableComponent, {
  TableComponentProps,
} from "@/components/tableComponent";
import { ElementRef, forwardRef } from "react";
import BaseModal from "../baseModal";

interface TableModalProps extends TableComponentProps {
  tableTitle: string;
  children: React.ReactNode;
}

const TableModal = forwardRef<
  ElementRef<typeof TableComponent>,
  TableModalProps
>(({ tableTitle, children, ...props }: TableModalProps, ref) => {
  return (
    <BaseModal>
      <BaseModal.Header description={"Add or edit your data"}>
        <div className="flex justify-center gap-2 align-baseline">
          <ForwardedIconComponent name="Table" />
          {tableTitle}
        </div>
      </BaseModal.Header>
      <BaseModal.Content>
        <TableComponent
          className="h-full w-full"
          ref={ref}
          {...props}
        ></TableComponent>
      </BaseModal.Content>
      <BaseModal.Footer submit={{ label: "close" }}></BaseModal.Footer>
      <BaseModal.Trigger asChild>{children}</BaseModal.Trigger>
    </BaseModal>
  );
});

export default TableModal;
