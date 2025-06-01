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
  dismissAll,
  isOutdated,
  isUserEdited,
  isBreakingChange,
  getValidationStatus,
  beta,
}: {
  nodeId: string;
  display_name: string;
  selected?: boolean;
  setBorderColor: (color: string) => void;
  frozen?: boolean;
  showNode: boolean;
  data: NodeDataType;
  buildStatus: BuildStatus;
  dismissAll: boolean;
  isOutdated: boolean;
  isUserEdited: boolean;
  isBreakingChange: boolean;
  getValidationStatus: (data) => VertexBuildTypeAPI | null;
  beta: boolean;
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
      dismissAll={dismissAll}
      isBreakingChange={isBreakingChange}
      beta={beta}
    />
  );
}

export default CustomNodeStatus;
