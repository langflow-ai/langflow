import {
  BaseEdge,
  type EdgeProps,
  getBezierPath,
  Position,
} from "@xyflow/react";
import IconComponent from "@/components/common/genericIconComponent";
import {
  ContextMenu,
  ContextMenuContent,
  ContextMenuItem,
  ContextMenuTrigger,
} from "@/components/ui/context-menu";
import useFlowStore from "@/stores/flowStore";
import { scapeJSONParse } from "@/utils/reactflowUtils";

const UNRECOGNIZED_DOM_PROPS = [
  "targetPosition",
  "sourcePosition",
  "pathOptions",
];

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
  const edges = useFlowStore((state) => state.edges);
  const setEdges = useFlowStore((state) => state.setEdges);

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

  const { animated, selectable, deletable, selected, ...domSafeProps } = props;

  //Remove unrecognized DOM props
  UNRECOGNIZED_DOM_PROPS.forEach((prop) => {
    if (prop in domSafeProps) {
      delete domSafeProps[prop];
    }
  });

  return (
    <>
      <BaseEdge
        path={targetHandleObject.output_types ? edgePathLoop : edgePath}
        strokeDasharray={targetHandleObject.output_types ? "5 5" : "0"}
        {...domSafeProps}
        data-animated={animated ? "true" : "false"}
        data-selectable={selectable ? "true" : "false"}
        data-deletable={deletable ? "true" : "false"}
        data-selected={selected ? "true" : "false"}
      />

      <ContextMenu>
        <ContextMenuTrigger asChild>
          <path
            className="react-flow__edge-interaction"
            d={targetHandleObject.output_types ? edgePathLoop : edgePath}
            strokeOpacity={0}
            strokeWidth={20}
            fill="none"
            data-testid={`edge-context-menu-trigger`}
          />
        </ContextMenuTrigger>
        <ContextMenuContent>
          <ContextMenuItem
            variant="destructive"
            onClick={() => {
              const newEdges = edges.filter((edge) => edge.id !== props.id);
              setEdges(newEdges);
            }}
            data-testid="context-menu-item-destructive"
          >
            <IconComponent name="Trash2" className="size-3.5 text-inherit" />
            <span className="text-xs">Delete</span>
          </ContextMenuItem>
        </ContextMenuContent>
      </ContextMenu>
    </>
  );
}
