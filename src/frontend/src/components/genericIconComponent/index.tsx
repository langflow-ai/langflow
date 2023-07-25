import { ReactElement, SVGProps, createElement } from "react";
import { IconComponentProps } from "../../types/components";
import { nodeIconsLucide } from "../../utils/styleUtils";

export default function IconComponent({
  name,
  className,
  iconColor,
}: IconComponentProps): JSX.Element {
  // MAYBE PROBLEM HERE?
  const TargetIcon = createElement(nodeIconsLucide[name] ?? nodeIconsLucide["unknown"], {
    className,
    style: { color: iconColor },
  });  
  return TargetIcon as JSX.Element
}
