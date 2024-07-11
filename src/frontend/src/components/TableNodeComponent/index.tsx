import BaseModal from "@/modals/baseModal";
import IconComponent from "../../components/genericIconComponent";
import { TableComponentType } from "../../types/components";
import TableComponent from "../tableComponent";
import { FormatColumns } from "@/utils/utils";

export default function TableNodeComponent({
    tableTitle,
    value,
    onChange,
    editNode = false,
    id = "",
    columns,
}: TableComponentType): JSX.Element {
    function deleteRow() { }
    function duplicateRow() { }
    function addRow() { }
    function editRow() { }

    const AgColumns = FormatColumns(columns);
    console.log("AgColumns", AgColumns);
    return (
        <div className={"flex w-full items-center"}>
            <div className="flex w-full items-center gap-3" data-testid={"div-" + id}>
                <BaseModal>
                    <BaseModal.Header description={"Add or edit your data"}>
                        <IconComponent name="Table" />
                        {tableTitle}
                    </BaseModal.Header>
                    <BaseModal.Content>
                        <TableComponent displayEmptyAlert={false} className="h-full w-full" columnDefs={AgColumns} rowData={[]}></TableComponent>
                    </BaseModal.Content>
                    <BaseModal.Footer submit={{ label: "close" }}></BaseModal.Footer>
                    <BaseModal.Trigger>
                        <div className="flex items-start justify-between align-middle">
                            <span>Edit Data</span>
                        </div>
                    </BaseModal.Trigger>
                </BaseModal>
            </div>
        </div>
    );
}
