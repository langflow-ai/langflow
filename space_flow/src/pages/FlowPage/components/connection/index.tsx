import { CSSProperties, FC } from 'react';
import { Node } from 'reactflow';

interface ConnectionLineComponentProps {
	fromX: number;
	fromY: number;
	fromPosition: string;
	toX: number;
	toY: number;
  fromNode:Node;
	toPosition: string;
	connectionLineType: string;
	connectionLineStyle: CSSProperties;
}

const ConnectionLineComponent = ({
	fromX,
	fromY,
	fromPosition,
	toX,
	toY,
	toPosition,
	connectionLineType,
  fromNode={},
	connectionLineStyle = {} // provide a default value for connectionLineStyle
}) => {
	return (
		<g>
			<path
				fill="none"
				stroke="#222"
				strokeWidth={1.5}
				className="animated"
				d={`M${fromX},${fromY} C ${fromX} ${toY} ${fromX} ${toY} ${toX},${toY}`}
				style={connectionLineStyle}
			/>
			<circle
				cx={toX}
				cy={toY}
				fill="#fff"
				r={3}
				stroke="#222"
				strokeWidth={1.5}
			/>
		</g>
	);
};

export default ConnectionLineComponent;
