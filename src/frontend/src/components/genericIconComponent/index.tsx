import { createElement } from "react";
import { IconComponentProps } from "../../types/components";
import { nodeIconsLucide } from "../../utils/styleUtils";

export default function IconComponent({
  name,
  className,
  iconColor,
}: IconComponentProps): JSX.Element {
  const TargetIcon = createElement(nodeIconsLucide[name], {
    className,
    style: { color: iconColor },
  });
  return TargetIcon as JSX.Element;
}
