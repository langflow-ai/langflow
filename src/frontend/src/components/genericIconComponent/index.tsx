import { IconComponentProps, IconProps } from "../../types/components";
import { nodeIconsLucide } from "../../utils";

export function IconFromLucide({
  name,
  style,
  iconColor,
}: IconProps): JSX.Element {
  const TargetIcon = nodeIconsLucide[name] ?? nodeIconsLucide["unknown"];
  return <TargetIcon className={style} style={{ color: iconColor }} />;
}

export default function IconComponent({
  name,
  style,
  iconColor,
}: IconComponentProps): JSX.Element {
  const TargetIcon = nodeIconsLucide[name] ?? nodeIconsLucide["unknown"];
  return <TargetIcon className={style} style={{ color: iconColor }} />;
}
