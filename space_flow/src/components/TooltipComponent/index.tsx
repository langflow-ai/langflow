import { LightTooltip } from "../LightTooltipComponent";

export default function Tooltip({ children, title }) {
  return <LightTooltip title={title} arrow>{children}</LightTooltip>;
}
