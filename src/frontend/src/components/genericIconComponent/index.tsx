import { IconComponentProps } from "../../types/components";
import { nodeIconsLucide } from "../../utils/styleUtils";

export default function IconComponent({
  name,
  className,
  iconColor,
}: IconComponentProps): JSX.Element {
  const TargetIcon = nodeIconsLucide[name] ?? nodeIconsLucide["unknown"];
  return (
    <TargetIcon
      strokeWidth={1.5}
      className={className}
      style={{ color: iconColor }}
    />
  );
}
