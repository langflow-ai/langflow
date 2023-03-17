import { useEffect, useState } from "react";
import { InputComponentType } from "../../types/components";
import { classNames } from "../../utils";

export default function InputComponent({
	value,
	onChange,
	disabled,
	password,
}: InputComponentType) {
	const [myValue, setMyValue] = useState(value ?? "");
	useEffect(() => {
		if (disabled) {
			setMyValue("");
			onChange("");
		}
	}, [disabled, onChange]);
	return (
		<div className={disabled ? "pointer-events-none cursor-not-allowed" : ""}>
			<input
				type="text"
				value={myValue}
				className={classNames(
					"block w-full form-input dark:bg-gray-900 dark:border-gray-600 rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm",
					disabled ? " bg-gray-200 dark:bg-gray-700" : "",
                    password?"password":""
				)}
				placeholder="Type a text"
				onChange={(e) => {
					setMyValue(e.target.value);
					onChange(e.target.value);
				}}
			/>
		</div>
	);
}
