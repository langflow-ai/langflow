import { BuildStatus } from "@/constants/enums";
import NodeStatus from "@/CustomNodes/GenericNode/components/NodeStatus";
import { VertexBuildTypeAPI } from "@/types/api";
import { NodeDataType } from "@/types/flow";

export function CustomNodeStatus({
  nodeId,
  display_name,
  selected,
  setBorderColor,
  frozen,
  showNode,
  data,
  buildStatus,
  isOutdated,
  isUserEdited,
  getValidationStatus,
  handleUpdateComponent,
}: {
  nodeId: string;
  display_name: string;
  selected?: boolean;
  setBorderColor: (color: string) => void;
  frozen?: boolean;
  showNode: boolean;
  data: NodeDataType;
  buildStatus: BuildStatus;
  isOutdated: boolean;
  isUserEdited: boolean;
  getValidationStatus: (data: NodeDataType) => VertexBuildTypeAPI | null;
  handleUpdateComponent: () => void;
}) {
  return (
    <NodeStatus
      nodeId={nodeId}
      display_name={display_name}
      selected={selected}
      setBorderColor={setBorderColor}
      frozen={frozen}
      showNode={showNode}
      data={data}
      buildStatus={buildStatus}
      isOutdated={isOutdated}
      isUserEdited={isUserEdited}
      getValidationStatus={getValidationStatus}
      handleUpdateComponent={handleUpdateComponent}
    />
  );
}

export default CustomNodeStatus;
