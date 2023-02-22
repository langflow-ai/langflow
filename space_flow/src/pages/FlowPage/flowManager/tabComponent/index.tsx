import { XMarkIcon } from "@heroicons/react/24/solid";
import { useContext } from "react";
import { TabsContext } from "../../../../contexts/tabsContext";
import { classNames } from "../../../../utils";

export default function TabComponent({ children, selected, id }) {
	const { removeFlow, flows } = useContext(TabsContext);
	return (
		<div
			className={classNames(
				selected ? " shadow-lg" : "bg-gray-300",
				"flex border-t border-l border-r border-black rounded-t-md shadow-sm cursor-pointer"
			)}
		>
			{children}
			{flows.length > 1 && (
				<XMarkIcon
					className="w-5 hover:text-red-500"
					onClick={() => removeFlow(id)}
				></XMarkIcon>
			)}
		</div>
	);
}
