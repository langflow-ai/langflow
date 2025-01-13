import useFlowStore from "@/stores/flowStore";
import { scapeJSONParse } from "@/utils/reactflowUtils";
import { BaseEdge, EdgeProps, getBezierPath, Position } from "@xyflow/react";

export function DefaultEdge({
  sourceHandleId,
  source,
  sourceX,
  sourceY,
  target,
  targetHandleId,
  targetX,
  targetY,
  ...props
}: EdgeProps) {
  const getNode = useFlowStore((state) => state.getNode);

  const sourceNode = getNode(source);
  const targetNode = getNode(target);

  const targetHandleObject = scapeJSONParse(targetHandleId!);

  const sourceXNew =
    (sourceNode?.position.x ?? 0) + (sourceNode?.measured?.width ?? 0);
  const targetXNew = targetNode?.position.x ?? 0;

  const edgePathLoop = `M ${sourceXNew} ${sourceY} C ${sourceXNew + 200} ${sourceY + 200}, ${targetXNew - 200} ${targetY + 200}, ${targetXNew} ${targetY}`;

  const [edgePath] = getBezierPath({
    sourceX: sourceXNew,
    sourceY,
    sourcePosition: Position.Right,
    targetPosition: Position.Left,
    targetX: targetXNew,
    targetY,
  });

  return (
    <BaseEdge
      path={targetHandleObject.output_types ? edgePathLoop : edgePath}
      strokeDasharray={targetHandleObject.output_types ? "5 5" : "0"}
      {...props}
    />
  );
}
