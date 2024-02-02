import { ConnectionLineComponentProps } from "reactflow";

const ConnectionLineComponent = ({
  fromX,
  fromY,
  toX,
  toY,
  connectionLineStyle = {}, // provide a default value for connectionLineStyle
}: ConnectionLineComponentProps): JSX.Element => {
  return (
    <g>
      <path
        fill="none"
        // ! Replace hash # colors here
        strokeWidth={2.5}
        className="animated stroke-[#7c3aed] "
        d={`M${fromX},${fromY} C ${fromX} ${toY} ${fromX} ${toY} ${toX},${toY}`}
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
