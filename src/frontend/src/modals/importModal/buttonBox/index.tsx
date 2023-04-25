import React, { ReactNode } from "react";
import { DocumentDuplicateIcon } from "@heroicons/react/solid";
import { classNames } from "../../../utils";
import Tooltip from "../../../components/TooltipComponent";

export default function ButtonBox({
	onClick,
	title,
	description,
	icon,
	bgColor,
	textColor,
	deactivate,
	size,
}: {
	onClick: () => void;
	title: string;
	description: string;
	icon: ReactNode;
	bgColor: string;
	textColor: string;
	deactivate?: boolean;
	size: "small" | "medium" | "big";
}) {
	let bigCircle: string;
	let smallCircle: string;
	let titleFontSize: string;
	let descriptionFontSize: string;
	let padding: string;
	let marginTop: string;
	let height: string;
	let widht: string;
	switch (size) {
		case "small":
			bigCircle = "h-12 w-12";
			smallCircle = "h-8 w-8";
			titleFontSize = "text-sm";
			descriptionFontSize = "text-xs";
			padding = "p-2";
			marginTop = "mt-2";
			height = "h-36";
			widht = "w-32";
			break;
		case "medium":
			bigCircle = "h-16 w-16";
			smallCircle = "h-12 w-12";
			titleFontSize = "text-base";
			descriptionFontSize = "text-sm";
			padding = "p-4";
			marginTop = "mt-3";
			height = "h-44";
			widht = "w-36";
			break;
		case "big":
			bigCircle = "h-20 w-20";
			smallCircle = "h-16 w-16";
			titleFontSize = "text-lg";
			descriptionFontSize = "text-sm";
			padding = "p-8";
			marginTop = "mt-6";
			height = "h-56";
			widht = "w-44";
			break;
		default:
			bigCircle = "h-20 w-20";
			smallCircle = "h-16 w-16";
			titleFontSize = "text-lg";
			descriptionFontSize = "text-sm";
			padding = "p-8";
			marginTop = "mt-6";
			height = "h-56";
			widht = "w-44";
			break;
	}
	return (
		<button disabled={deactivate} onClick={onClick}>
			<Tooltip title={description} placement="bottom">
				<div
					className={classNames(
						"col-span-1 flex flex-col  divide-y divide-gray-200 rounded-lg text-center shadow border border-gray-300 hover:shadow-lg transform hover:scale-105",
						bgColor,
						height,
						widht
					)}
				>
					<div className={`flex flex-1 flex-col ${padding}`}>
						<div
							className={`mx-auto flex items-center justify-center ${bigCircle} bg-white/30 rounded-full`}
						>
							<div
								className={`mx-auto flex items-center justify-center ${smallCircle} bg-white rounded-full`}
							>
								<div className={textColor}>{icon}</div>
							</div>
						</div>
						<h3
							className={classNames(
								"font-semibold text-white",
								titleFontSize,
								marginTop
							)}
						>
							{title}
						</h3>
						<div className="mt-1 flex flex-grow flex-col justify-between">
							<dt className="sr-only">{title}</dt>
							{/* <dd
								className={classNames(
									"text-gray-100 line-clamp-2",
									descriptionFontSize
								)}
							>
								{deactivate ? "Coming soon" : description}
							</dd> */}
						</div>
					</div>
				</div>
			</Tooltip>
		</button>
	);
}
