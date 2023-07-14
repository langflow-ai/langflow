import { IconComponentProps, IconProps } from "../../types/components";
import { nodeIconsLucide, svgIcons } from "../../utils";

export function IconFromLucide({ name }: IconProps): JSX.Element {
  const TargetIcon = nodeIconsLucide[name] ?? nodeIconsLucide["unknown"];
  return <TargetIcon />;
}

export function IconFromSvg({ name }: IconProps): JSX.Element {
  const TargetSvg = svgIcons[name] ?? nodeIconsLucide["unknown"];
  return <TargetSvg />;
}

export default function IconComponent({
  method,
  name,
}: IconComponentProps): JSX.Element {
  switch (method) {
    case "SVG":
      return <IconFromSvg name={name} />;
    case "LUCIDE":
      return <IconFromLucide name={name} />;
    default:
      console.error("IconComponent: invalid method");
      return <IconFromLucide name={"unknown"} />;
  }
}
