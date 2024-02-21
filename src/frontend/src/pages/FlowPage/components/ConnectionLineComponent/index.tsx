import {
  ConnectionLineComponentProps,
  Position,
  getBezierPath,
} from "reactflow";

const ConnectionLineComponent = ({
  fromX,
  fromY,
  toX,
  toY,
  fromHandle,
  connectionLineStyle = {}, // provide a default value for connectionLineStyle
}: ConnectionLineComponentProps): JSX.Element => {

  const newFromX =
    fromX +
    ((fromHandle?.width ?? 0) / 2) * (fromHandle?.position === "left" ? -1 : 1);

  const [bezierPath] = getBezierPath({
    sourceX: newFromX,
    sourceY: fromY,
    sourcePosition: fromHandle?.position ?? Position.Left,
    targetX: toX,
    targetY: toY,
    targetPosition:
      (fromHandle?.position ?? Position.Left) === Position.Left
        ? Position.Right
        : Position.Left,
  });
  return (
    <g>
      <path
        fill="none"
        // ! Replace hash # colors here
        strokeWidth={3.5}
        className="animated stroke-[#7c3aed] "
        d={bezierPath}
        style={connectionLineStyle}
      />
      <circle
        cx={toX}
        cy={toY}
        fill="#ffffff"
        r={2}
        stroke="#7c3aed"
        className=""
        strokeWidth={5}
      />
    </g>
  );
};

export default ConnectionLineComponent;
