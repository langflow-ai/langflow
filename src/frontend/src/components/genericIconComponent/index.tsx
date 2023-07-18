import { IconComponentProps } from "../../types/components";
import { nodeIconsLucide } from "../../utils";

export default function IconComponent({
  name,
  className,
  iconColor,
}: IconComponentProps): JSX.Element {
  const TargetIcon = nodeIconsLucide[name] ?? nodeIconsLucide["unknown"];
  return <TargetIcon className={className} style={{ color: iconColor }} />;
}
