import useFlowStore from "@/stores/flowStore";
import { scapeJSONParse } from "@/utils/reactflowUtils";
import {
  BaseEdge,
  type EdgeProps,
  getBezierPath,
  Position,
} from "@xyflow/react";

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
    (sourceNode?.position.x ?? 0) + (sourceNode?.measured?.width ?? 0) + 7;
  const targetXNew = (targetNode?.position.x ?? 0) - 7;

  const distance = 200 + 0.1 * ((sourceXNew - targetXNew) / 2);

  const zeroOnNegative =
    (1 +
      (1 - Math.exp(-0.01 * Math.abs(sourceXNew - targetXNew))) *
        (sourceXNew - targetXNew >= 0 ? 1 : -1)) /
    2;

  const distanceY =
    200 -
    200 * (1 - zeroOnNegative) +
    0.3 * Math.abs(targetY - sourceY) * zeroOnNegative;

  const sourceDistanceY =
    200 -
    200 * (1 - zeroOnNegative) +
    0.3 * Math.abs(sourceY - targetY) * zeroOnNegative;

  const targetYNew = targetY + 1;
  const sourceYNew = sourceY + 1;

  const edgePathLoop = `M ${sourceXNew} ${sourceYNew} C ${sourceXNew + distance} ${sourceYNew + sourceDistanceY}, ${targetXNew - distance} ${targetYNew + distanceY}, ${targetXNew} ${targetYNew}`;

  const [edgePath] = getBezierPath({
    sourceX: sourceXNew,
    sourceY: sourceYNew,
    sourcePosition: Position.Right,
    targetPosition: Position.Left,
    targetX: targetXNew,
    targetY: targetYNew,
  });

  const {
    animated,
    selectable,
    deletable,
    sourcePosition,
    targetPosition,
    pathOptions,
    selected,
    ...domSafeProps
  } = props;

  return (
    <BaseEdge
      path={targetHandleObject.output_types ? edgePathLoop : edgePath}
      strokeDasharray={targetHandleObject.output_types ? "5 5" : "0"}
      {...domSafeProps}
      data-animated={animated ? "true" : "false"}
      data-selectable={selectable ? "true" : "false"}
      data-deletable={deletable ? "true" : "false"}
      data-selected={selected ? "true" : "false"}
    />
  );
}
