import React, { ReactNode, useEffect, useRef, useState } from "react";
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
  let minTitleFontSize: number;
  let descriptionFontSize: string;
  let padding: string;
  let marginTop: string;
  let height: string;
  let width: string;
  let textHeight: number;
  let textWidth: number;
  const [truncate, setTruncate] = useState<boolean>(false);
  switch (size) {
    case "small":
      bigCircle = "h-12 w-12";
      smallCircle = "h-8 w-8";
      minTitleFontSize =9;
      descriptionFontSize = "text-xs";
      padding = "p-2 py-3";
      marginTop = "mt-2";
      height = "h-36";
      textHeight = 70;
      textWidth = 40;
      width = "w-32";
      break;
    case "medium":
      bigCircle = "h-16 w-16";
      smallCircle = "h-12 w-12";
      minTitleFontSize = 11;
      descriptionFontSize = "text-sm";
      padding = "p-4 py-5";
      marginTop = "mt-3";
      textHeight = 112;
      textWidth = 162;
      height = "h-44";
      width = "w-36";
      break;
    case "big":
      bigCircle = "h-20 w-20";
      smallCircle = "h-16 w-16";
      minTitleFontSize = 12;
      descriptionFontSize = "text-sm";
      padding = "p-8 py-10";
      marginTop = "mt-6";
      height = "h-56";
      width = "w-44";
      break;
    default:
      bigCircle = "h-20 w-20";
      smallCircle = "h-16 w-16";
      minTitleFontSize = 12;
      descriptionFontSize = "text-sm";
      padding = "p-8 py-10";
      marginTop = "mt-6";
      height = "h-56";
      width = "w-44";
      break;
  }

  const [fontSize, setFontSize] = useState<number>(16); // Initial font size value

  const titleRef = useRef<HTMLHeadingElement>(null);
  const parentDivRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
	const textElement = titleRef.current;
	const parentDivElement = parentDivRef.current;
  
	if (!textElement || !parentDivElement) return;
  
	const parentDivHeight = parentDivElement.offsetHeight;
	const parentDivWidth = parentDivElement.offsetWidth;
	let textElementHeight = textElement.scrollHeight;
	let textElementWidth = textElement.scrollWidth;
  
	if (textElementHeight > parentDivHeight || textElementWidth > parentDivWidth && fontSize > minTitleFontSize) {
	  let newFontSize = fontSize;
  
	  while (textElementHeight > parentDivHeight || textElementWidth > parentDivWidth) {
		newFontSize -= 1;
		textElement.style.fontSize = `${newFontSize}px`;
		textElementHeight = textElement.scrollHeight;
		textElementWidth = textElement.scrollWidth;
	  }
    if(newFontSize <= minTitleFontSize){
      setTruncate(true);
      setFontSize(minTitleFontSize);
    }
    else{
      setFontSize(newFontSize);
    }
	}
  }, [title, size, fontSize]);
  

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
          className={`flex items-center justify-center ${bigCircle} bg-white/30 dark:bg-white/30 rounded-full mb-1`}
        >
          <div
            className={`flex items-center justify-center ${smallCircle} bg-white dark:bg-white/80 rounded-full`}
          >
            <div className={textColor}>{icon}</div>
          </div>
        </div>
		<div ref={parentDivRef} className="w-full h-1/2 mt-auto">
		<div
          ref={titleRef}
          className={classNames(truncate?"truncate":"",
            " font-semibold text-white h-full dark:text-white/80",
          )}        >
          {title}
        </div>
		</div>
      </div>
    </button>
  );
}
