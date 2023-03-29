import { DocumentMagnifyingGlassIcon } from "@heroicons/react/24/outline";
import { useContext, useEffect, useState } from "react";
import { TextAreaComponentType } from "../../types/components";

export default function InputFileComponent({
	value,
	onChange,
	disabled,
}: TextAreaComponentType) {
	const [myValue, setMyValue] = useState(value);
	useEffect(() => {
		if (disabled) {
			setMyValue("");
			onChange("");
		}
	}, [disabled, onChange]);

	const handleButtonClick = () => {
		const input = document.createElement("input");
		input.type = "file";
		// input.accept = ".yaml";
		input.style.display = "none";
		input.onchange = (e: Event) => {
			const file = (e.target as HTMLInputElement).files?.[0];
			//check file type
            // file.name.endsWith(".yaml")
            if (file) {
				setMyValue(file.name);
				onChange(file.name);
			}
		};
		input.click();
	};

	return (
		<div
			className={
				disabled ? "pointer-events-none cursor-not-allowed w-full" : "w-full"
			}
		>
			<div className="w-full flex items-center gap-3">
				<span
					className={
						"truncate block max-w-full text-gray-500 px-3 py-2 rounded-md border border-gray-300 dark:border-gray-700 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm" +
						(disabled ? " bg-gray-200" : "")
					}
				>
					{myValue !== "" ? myValue : "No file"}
				</span>
				<button
                onClick={handleButtonClick}
                >
					<DocumentMagnifyingGlassIcon className="w-6 h-6 hover:text-blue-600" />
				</button>
			</div>
		</div>
	);
}
