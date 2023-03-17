import { ReactElement } from "react";
import { LightTooltip } from "../LightTooltipComponent";

export default function Tooltip({ children, title }:{children:ReactElement,title:string}) {
  return <LightTooltip title={title} arrow>{children}</LightTooltip>;
}
