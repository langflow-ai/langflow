import { TooltipComponentType } from "../../types/components";
import { LightTooltip } from "../LightTooltipComponent";

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
