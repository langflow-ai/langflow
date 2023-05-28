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
        stroke="#222"
        strokeWidth={1.5}
        className="animated dark:stroke-gray-400"
        d={`M${fromX},${fromY} C ${fromX} ${toY} ${fromX} ${toY} ${toX},${toY}`}
        style={connectionLineStyle}
      />
      <circle
        cx={toX}
        cy={toY}
        fill="#fff"
        r={3}
        stroke="#222"
        className="dark:stroke-gray-400 dark:fill-gray-800"
        strokeWidth={1.5}
      />
    </g>
  );
};

export default ConnectionLineComponent;
