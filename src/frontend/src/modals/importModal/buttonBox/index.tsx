import React, { ReactNode } from "react";
import { DocumentDuplicateIcon } from "@heroicons/react/solid";
import { classNames } from "../../../utils";

export default function ButtonBox({
	onClick,
	title,
	description,
	icon,
	bgColor,
	textColor,
	deactivate
}: {
	onClick: () => void;
	title: string;
	description: string;
	icon: ReactNode;
	bgColor: string;
	textColor: string;
	deactivate?:boolean;
}) {
	return (
		<button disabled={deactivate} onClick={onClick}>
			<div
				className={classNames(
					"col-span-1 flex flex-col divide-y divide-gray-200 rounded-lg text-center shadow border border-gray-300 hover:shadow-lg transform hover:scale-105",
					bgColor
				)}
			>
				<div className="flex flex-1 flex-col p-8">
					<div className="mx-auto flex items-center justify-center h-20 w-20 bg-white/30 rounded-full">
						<div className="mx-auto flex items-center justify-center h-16 w-16 bg-white rounded-full">
                            <div className={textColor}>
                                {icon}
                            </div>
						</div>
					</div>
					<h3 className="mt-6 text-lg font-semibold text-white">{title}</h3>
					<div className="mt-1 flex flex-grow flex-col justify-between">
						<dt className="sr-only">{title}</dt>
						<dd className="text-sm text-gray-100">{deactivate? "cooming soon":description}</dd>
					</div>
				</div>
			</div>
		</button>
	);
}
