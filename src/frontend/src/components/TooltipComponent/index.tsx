import { TooltipComponentType } from "../../types/components";
import { LightTooltip } from "../LightTooltipComponent";

export default function Tooltip({
  children,
  title,
  placement,
}: TooltipComponentType): JSX.Element {
  return (
    <LightTooltip placement={placement} title={title} arrow>
      {children}
    </LightTooltip>
  );
}
