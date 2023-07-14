import { IconComponentProps, IconProps } from "../../types/components";
import { nodeIconsLucide, svgIcons } from "../../utils";

export function IconFromLucide({
  name,
  style,
}: IconProps): JSX.Element {
  const TargetIcon = nodeIconsLucide[name] ?? nodeIconsLucide["unknown"];
  return <TargetIcon className={ style } />;
}

export function IconFromSvg({
  name,
  style
}: IconProps): JSX.Element {
  const TargetSvg = svgIcons[name] ?? nodeIconsLucide["unknown"];
  return <TargetSvg className={ style } />;
}

export default function IconComponent({
  method,
  name,
  style,
}: IconComponentProps): JSX.Element {
  switch (method) {
    case "SVG":
      return <IconFromSvg name={name} style={ style } />;
    case "LUCIDE":
      return <IconFromLucide name={name} style={ style } />;
    default:
      console.error("IconComponent: invalid method");
      return <IconFromLucide name={"unknown"} style={"unknown"} />;
  }
}
