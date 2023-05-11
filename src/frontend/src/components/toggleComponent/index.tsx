import { Switch } from "@headlessui/react";
import { classNames } from "../../utils";
import { useEffect } from "react";
import { ToggleComponentType } from "../../types/components";

export default function ToggleComponent({
	enabled,
	setEnabled,
	disabled,
}: ToggleComponentType) {
	useEffect(() => {
		if (disabled) {
			setEnabled(false);
		}
	}, [disabled, setEnabled]);
	return (
		<div className={disabled ? "pointer-events-none cursor-not-allowed" : ""}>
			<Switch
				checked={enabled}
				onChange={(x: boolean) => {
					setEnabled(x);
				}}
				className={classNames(
					enabled ? "bg-indigo-600" : "bg-gray-200 dark:bg-gray-600",
					"relative inline-flex h-6 w-11 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out "
				)}
			>
				<span className="sr-only">Use setting</span>
				<span
					className={classNames(
						enabled ? "translate-x-5" : "translate-x-0",
						"pointer-events-none relative inline-block h-5 w-5 transform rounded-full  shadow ring-0 transition duration-200 ease-in-out",
						disabled
							? "bg-gray-200 dark:bg-gray-600"
							: "bg-white dark:bg-gray-800"
					)}
				>
					<span
						className={classNames(
							enabled
								? "opacity-0 ease-out duration-100"
								: "opacity-100 ease-in duration-200",
							"absolute inset-0 flex h-full w-full items-center justify-center transition-opacity"
						)}
						aria-hidden="true"
					>
						<svg
							className="h-3 w-3 text-gray-400"
							fill="none"
							viewBox="0 0 12 12"
						>
							<path
								d="M4 8l2-2m0 0l2-2M6 6L4 4m2 2l2 2"
								stroke="currentColor"
								strokeWidth={2}
								strokeLinecap="round"
								strokeLinejoin="round"
							/>
						</svg>
					</span>
					<span
						className={classNames(
							enabled
								? "opacity-100 ease-in duration-200"
								: "opacity-0 ease-out duration-100",
							"absolute inset-0 flex h-full w-full items-center justify-center transition-opacity"
						)}
						aria-hidden="true"
					>
						<svg
							className="h-3 w-3 text-indigo-600"
							fill="currentColor"
							viewBox="0 0 12 12"
						>
							<path d="M3.707 5.293a1 1 0 00-1.414 1.414l1.414-1.414zM5 8l-.707.707a1 1 0 001.414 0L5 8zm4.707-3.293a1 1 0 00-1.414-1.414l1.414 1.414zm-7.414 2l2 2 1.414-1.414-2-2-1.414 1.414zm3.414 2l4-4-1.414-1.414-4 4 1.414 1.414z" />
						</svg>
					</span>
				</span>
			</Switch>
		</div>
	);
}
