import { ColDef } from "ag-grid-community";
import { useState } from "react";
import useHandleNodeClass from "../../CustomNodes/hooks/use-handle-node-class";
import TableComponent from "../../components/tableComponent";
import { Badge } from "../../components/ui/badge";
import { Button } from "../../components/ui/button";
import { useDarkStore } from "../../stores/darkStore";
import { APIClassType } from "../../types/api";
import { NodeDataType } from "../../types/flow";
import BaseModal from "../baseModal";
import useColumnDefs from "./hooks/use-column-defs";
import useRowData from "./hooks/use-row-data";

const EditNodeModal = ({
  nodeLength,
  open,
  setOpen,
  data,
}: {
  nodeLength: number;
  open: boolean;
  setOpen: (open: boolean) => void;
  data: NodeDataType;
}) => {
  const isDark = useDarkStore((state) => state.dark);

  const { handleNodeClass: handleNodeClassHook } = useHandleNodeClass(data.id);

  const [nodeClass, setNodeClass] = useState<APIClassType>(data.node!);

  const handleNodeClass = (newNodeClass: APIClassType, type?: string) => {
    handleNodeClassHook(newNodeClass, type);
    setNodeClass(newNodeClass);
  };

  const rowData = useRowData(data, nodeClass, open);

  const columnDefs: ColDef[] = useColumnDefs(
    nodeClass,
    handleNodeClass,
    data.id,
    open,
  );

  return (
    <BaseModal key={data.id} open={open} setOpen={setOpen}>
      <BaseModal.Trigger>
        <></>
      </BaseModal.Trigger>
      <BaseModal.Header description={data.node?.description!}>
        <span className="pr-2">{data.node?.display_name ?? data.type}</span>
        <div>
          <Badge size="sm" variant={isDark ? "gray" : "secondary"}>
            ID: {data.id}
          </Badge>
        </div>
      </BaseModal.Header>
      <BaseModal.Content>
        <div className="flex h-full flex-col">
          <div className="h-full">
            {nodeLength > 0 && (
              <TableComponent
                key={"editNode"}
                tooltipShowDelay={0.5}
                columnDefs={columnDefs}
                rowData={rowData}
              />
            )}
          </div>
        </div>
      </BaseModal.Content>
      <BaseModal.Footer>
        <div className="flex w-full justify-end gap-2 pt-2">
          <Button onClick={() => setOpen(false)}>Close</Button>
        </div>
      </BaseModal.Footer>
    </BaseModal>
  );
};

export default EditNodeModal;
