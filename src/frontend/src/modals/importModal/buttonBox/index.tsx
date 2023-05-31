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
      width = "w-32";
      break;
    case "medium":
      bigCircle = "h-16 w-16";
      smallCircle = "h-12 w-12";
      titleFontSize = "text-base";
      descriptionFontSize = "text-sm";
      padding = "p-4 py-5";
      marginTop = "mt-3";
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
        <div className="w-full mt-auto mb-auto">
          <h3
            className={classNames(
              "w-full font-semibold break-words text-white dark:text-white/80 truncate-multiline",
              titleFontSize,
              marginTop
            )}
          >
            {title}
          </h3>
        </div>
      </div>
    </button>
  );
}
