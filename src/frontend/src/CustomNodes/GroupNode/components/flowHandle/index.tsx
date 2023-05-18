import { Handle, Position, useUpdateNodeInternals } from "reactflow";
import Tooltip from "../../../../components/TooltipComponent";
import { classNames, isValidConnection } from "../../../../utils";
import { useContext, useEffect, useRef, useState } from "react";
import { typesContext } from "../../../../contexts/typesContext";
import { FlowHandleType, ParameterComponentType } from "../../../../types/components";


export default function FlowHandle({
	left,
	id,
	data,
	tooltipTitle,
	title,
	color,
	required = false,
}: FlowHandleType) {
	const ref = useRef(null);
	const updateNodeInternals = useUpdateNodeInternals();
	const [position, setPosition] = useState(0);
	useEffect(() => {
		if (ref.current && ref.current.offsetTop && ref.current.clientHeight) {
			setPosition(ref.current.offsetTop + ref.current.clientHeight / 2);
			updateNodeInternals(data.id);
		}
	}, [data.id, ref, updateNodeInternals]);

	useEffect(() => {
		updateNodeInternals(data.id);
	}, [data.id, position, updateNodeInternals]);

	const { reactFlowInstance } = useContext(typesContext);

	return (
		<div
			ref={ref}
			className="w-full flex flex-wrap justify-between items-center bg-gray-50 dark:bg-gray-800 dark:text-white mt-1 px-5 py-2"
		>
			<>
				<div className={"text-sm truncate w-full " + (left ? "" : "text-end")}>
					{title}
					<span className="text-red-600">{required ? " *" : ""}</span>
				</div>
					<Tooltip title={tooltipTitle + (required ? " (required)" : "")}>
						<Handle
							type={left ? "target" : "source"}
							position={left ? Position.Left : Position.Right}
							id={id}
							isValidConnection={(connection) =>
								isValidConnection(connection, reactFlowInstance)
							}
							className={classNames(
								left ? "-ml-0.5 " : "-mr-0.5 ",
								"w-3 h-3 rounded-full border-2 bg-white dark:bg-gray-800"
							)}
							style={{
								borderColor: color,
								top: position,
							}}
						></Handle>
					</Tooltip>
			</>
		</div>
	);
}
