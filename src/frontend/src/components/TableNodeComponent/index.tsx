import BaseModal from "@/modals/baseModal";
import { TableComponentType } from "../../types/components";
import TableComponent from "../tableComponent";
import IconComponent from "../../components/genericIconComponent";

export default function TableNodeComponent({
    tableTitle,
    value,
    onChange,
    editNode = false,
    id = "",
    columns
}: TableComponentType): JSX.Element {
    function deleteRow() {}
    function duplicateRow() {}
    function addRow() {}
    function editRow() {}
    return (
        <div className={"flex w-full items-center"}>
            <div className="flex w-full items-center gap-3" data-testid={"div-" + id}>
                <BaseModal>
                    <BaseModal.Header description={"Add or edit your data"}>
                    <IconComponent name="Table"/>
                    {tableTitle}
                    </BaseModal.Header>
                    <TableComponent columnDefs={columns} rowData={value}>
                    </TableComponent>
                    <BaseModal.Footer submit={{label:"close"}}
                    ></BaseModal.Footer >
                    <BaseModal.Trigger>
                    <div className="flex justify-between align-middle items-start">
                        <span>Edit Data</span>
                    </div>
                    </BaseModal.Trigger>
                </BaseModal>
            </div>
        </div>
    );
}
