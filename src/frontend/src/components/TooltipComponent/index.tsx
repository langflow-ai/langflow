import { ReactElement } from "react";
import { LightTooltip } from "../LightTooltipComponent";
import { TooltipComponentType } from "../../types/components";

export default function Tooltip({
  children,
  title,
  placement,
}: TooltipComponentType) {
  return (
    <LightTooltip placement={placement} title={title} arrow>
      {children}
    </LightTooltip>
  );
}
