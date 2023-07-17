import { IconComponentProps, IconProps } from "../../types/components";
import { nodeIconsLucide } from "../../utils";

export function IconFromLucide({
  name,
  style,
  iconColor,
}: IconProps): JSX.Element {
  const TargetIcon = nodeIconsLucide[name] ?? nodeIconsLucide["unknown"];
  return <TargetIcon className={ style } style={{ color: iconColor }} />;
}

export default function IconComponent({
  method,
  name,
  style,
  iconColor,
}: IconComponentProps): JSX.Element {
  switch (method) {
    case "LUCIDE":
      return <IconFromLucide name={name} style={ style } iconColor={ iconColor } />;
    default:
      console.error("IconComponent: invalid method");
      return <IconFromLucide name={"unknown"} style={"unknown"} />;
  }
}
