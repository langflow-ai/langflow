import React, { ReactNode, useEffect } from "react";
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
	let width: string;
	let textHeight: number;
	let textWidth: number;
	switch (size) {
		case "small":
			bigCircle = "h-12 w-12";
			smallCircle = "h-8 w-8";
			titleFontSize = "text-sm";
			descriptionFontSize = "text-xs";
			padding = "p-2 py-3";
			marginTop = "mt-2";
			height = "h-36";
			textHeight=70;
			textWidth=80;
			width = "w-32";
			break;
		case "medium":
			bigCircle = "h-16 w-16";
			smallCircle = "h-12 w-12";
			titleFontSize = "text-base";
			descriptionFontSize = "text-sm";
			padding = "p-4 py-5";
			marginTop = "mt-3";
			textHeight=112;
			textWidth=162;
			height = "h-44";
			width = "w-36";
			break;
		case "big":
			bigCircle = "h-20 w-20";
			smallCircle = "h-16 w-16";
			titleFontSize = "text-lg";
			descriptionFontSize = "text-sm";
			padding = "p-8 py-10";
			marginTop = "mt-6";
			height = "h-56";
			width = "w-44";
			break;
		default:
			bigCircle = "h-20 w-20";
			smallCircle = "h-16 w-16";
			titleFontSize = "text-lg";
			descriptionFontSize = "text-sm";
			padding = "p-8 py-10";
			marginTop = "mt-6";
			height = "h-56";
			width = "w-44";
			break;
	}

	const titleRef = React.useRef<HTMLHeadingElement>(null);

	useEffect(() => {
		const resizeFont = () => {
			const titleElement = titleRef.current;
			if (titleElement) {
			  const containerWidth = titleElement.offsetWidth;
			  const containerHeight = titleElement.offsetHeight;
		  
			  const titleComputedStyle = window.getComputedStyle(titleElement);
			  const titleWidth = titleElement.getBoundingClientRect().width;
		  
			  const currentFontSize = parseFloat(titleComputedStyle.fontSize);
		  
			  const desiredWidth = textWidth - 10; // Subtracting the desired padding
		  
			  // Calculate the desired font size based on the adjusted width
			  let desiredFontSize = currentFontSize * (desiredWidth / titleWidth);
		  
			  // Adjust the desired font size to fit within the container height, if needed
			  const maxHeight = containerHeight - 10; // Subtracting the desired top padding
			  const maxHeightFontSize = maxHeight * 0.8; // Adjust the scaling factor as needed
			  desiredFontSize = Math.min(desiredFontSize, maxHeightFontSize);
		  
			  // Apply the desired font size and padding to the title element
			  titleElement.style.fontSize = `${desiredFontSize}px`;
			  titleElement.style.paddingLeft = '5px';
			  titleElement.style.paddingRight = '5px';
			}
		  };
		  
	  
		resizeFont();
		window.addEventListener("resize", resizeFont);
		return () => {
		  window.removeEventListener("resize", resizeFont);
		};
	  }, []);
	  
	return (
		<button disabled={deactivate} onClick={onClick}>
				<div
					className={classNames(
						"flex flex-col justify-center items-center rounded-lg text-center shadow border border-gray-300 dark:border-gray-800 hover:shadow-lg transform hover:scale-105",
						bgColor,
						height,
						width,
						padding
					)}
				>
						<div
							className={`flex items-center justify-center ${bigCircle} bg-white/30 dark:bg-white/30 rounded-full`}
						>
							<div
								className={`flex items-center justify-center ${smallCircle} bg-white dark:bg-white/80 rounded-full`}
							>
								<div className={textColor}>{icon}</div>
							</div>
						</div>
						<h3
						 ref={titleRef}
							className={classNames(
								" font-semibold text-white dark:text-white/80",

								marginTop
							)}
						>
							{title}
						</h3>
				</div>
		</button>
	);
}
