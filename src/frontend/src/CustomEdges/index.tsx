import useFlowStore from "@/stores/flowStore";
import { BaseEdge, EdgeProps, getBezierPath, Position } from "reactflow";

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

  const sourceXNew = (sourceNode?.position.x ?? 0) + (sourceNode?.width ?? 0);
  const targetXNew = targetNode?.position.x ?? 0;

  const [edgePath] = getBezierPath({
    sourceX: sourceXNew,
    sourceY,
    sourcePosition: Position.Right,
    targetPosition: Position.Left,
    targetX: targetXNew,
    targetY,
  });

  return <BaseEdge path={edgePath} {...props} />;
}
