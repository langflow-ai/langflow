import { ColDef } from "ag-grid-community";
import { forwardRef, useState } from "react";
import { useUpdateNodeInternals } from "reactflow";
import TableComponent from "../../components/tableComponent";
import { Badge } from "../../components/ui/badge";
import { Button } from "../../components/ui/button";
import { useDarkStore } from "../../stores/darkStore";
import useFlowStore from "../../stores/flowStore";
import useFlowsManagerStore from "../../stores/flowsManagerStore";
import { APIClassType } from "../../types/api";
import { NodeDataType } from "../../types/flow";
import {
  debouncedHandleUpdateValues,
  handleUpdateValues,
} from "../../utils/parameterUtils";
import BaseModal from "../baseModal";
import useColumnDefs from "./hooks/use-column-defs";
import useHandleChangeAdvanced from "./hooks/use-handle-change-advanced";
import useHandleOnNewValue from "./hooks/use-handle-new-value";
import useHandleNodeClass from "./hooks/use-handle-node-class";
import useRowData from "./hooks/use-row-data";

const EditNodeModal = forwardRef(
  (
    {
      nodeLength,
      open,
      setOpen,
      data,
    }: {
      nodeLength: number;
      open: boolean;
      setOpen: (open: boolean) => void;
      data: NodeDataType;
    },
    ref,
  ) => {
    const isDark = useDarkStore((state) => state.dark);
    const setNode = useFlowStore((state) => state.setNode);
    const takeSnapshot = useFlowsManagerStore((state) => state.takeSnapshot);
    const updateNodeInternals = useUpdateNodeInternals();

    const { handleOnNewValue: handleOnNewValueHook } = useHandleOnNewValue(
      data,
      takeSnapshot,
      handleUpdateValues,
      debouncedHandleUpdateValues,
      setNode,
    );

    const { handleNodeClass: handleNodeClassHook } = useHandleNodeClass(
      data,
      takeSnapshot,
      setNode,
      updateNodeInternals,
    );

    const [nodeClass, setNodeClass] = useState<APIClassType>(data.node!);

    const handleNodeClass = (
      newNodeClass: APIClassType,
      name: string,
      code: string,
      type?: string,
    ) => {
      handleNodeClassHook(newNodeClass, name, code, type);
      setNodeClass(newNodeClass);
    };

    const { handleChangeAdvanced: handleChangeAdvancedHook } =
      useHandleChangeAdvanced(data, takeSnapshot, setNode, updateNodeInternals);

    const rowData = useRowData(data, nodeClass, open);

    const columnDefs: ColDef[] = useColumnDefs(
      nodeClass,
      handleOnNewValueHook,
      handleNodeClass,
      handleChangeAdvancedHook,
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
  },
);

export default EditNodeModal;
