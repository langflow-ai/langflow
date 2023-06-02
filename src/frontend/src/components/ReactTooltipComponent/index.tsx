"use client";
import type { FC } from "react";
import React from "react";
import { Tooltip as ReactTooltip } from "react-tooltip";
import "react-tooltip/dist/react-tooltip.css";
import { classNames } from "../../utils";

type TooltipProps = {
  selector: string;
  content?: string;
  disabled?: boolean;
  htmlContent?: React.ReactNode;
  className?: string; // This should use !impornant to override the default styles eg: '!bg-white'
  position?: "top" | "right" | "bottom" | "left";
  clickable?: boolean;
  children: React.ReactNode;
  delayShow?: number;
};

const TooltipReact: FC<TooltipProps> = ({
  selector,
  content,
  disabled,
  position = "top",
  children,
  htmlContent,
  className,
  clickable,
  delayShow,
}) => {
  return (
    <div className="tooltip-container">
      {React.cloneElement(children as React.ReactElement, {
        "data-tooltip-id": selector,
      })}
      <ReactTooltip
        id={selector}
        content={content}
        className={classNames(
          "!bg-white !text-xs !font-normal !text-gray-700 !shadow-md !opacity-100 z-[9999]",
          className
        )}
        place={position}
        clickable={clickable}
        isOpen={disabled ? false : undefined}
        delayShow={delayShow}
        positionStrategy="absolute"
        float={true}
      >
        {htmlContent && htmlContent}
      </ReactTooltip>
    </div>
  );
};

export default TooltipReact;
