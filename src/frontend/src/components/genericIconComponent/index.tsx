import { IconComponentProps } from "../../types/components";
import { nodeIconsLucide } from "../../utils/styleUtils";

export default function IconComponent({
  name,
  className,
  iconColor,
}: IconComponentProps): JSX.Element {
  // MAYBE PROBLEM HERE?
  const TargetIcon = nodeIconsLucide[name] ?? nodeIconsLucide["unknown"];
  return <TargetIcon className={className} style={{ color: iconColor }} />;
}
