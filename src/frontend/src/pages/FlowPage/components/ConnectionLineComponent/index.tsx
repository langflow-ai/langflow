import { ConnectionLineComponentProps } from "reactflow";

const ConnectionLineComponent = ({
  fromX,
  fromY,
  toX,
  toY,
  connectionLineStyle = {}, // provide a default value for connectionLineStyle
}: ConnectionLineComponentProps) => {
  return (
    <g>
      <path
        fill="none"
        strokeWidth={1.5}
        className="animated stroke-muted-foreground "
        d={`M${fromX},${fromY} C ${fromX} ${toY} ${fromX} ${toY} ${toX},${toY}`}
        style={connectionLineStyle}
      />
      <circle
        cx={toX}
        cy={toY}
        r={3}
        className="stroke-muted-foreground fill-background"
        strokeWidth={1.5}
      />
    </g>
  );
};

export default ConnectionLineComponent;
