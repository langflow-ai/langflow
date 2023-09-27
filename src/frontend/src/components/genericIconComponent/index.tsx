import { forwardRef } from "react";
import { IconComponentProps } from "../../types/components";
import { nodeIconsLucide } from "../../utils/styleUtils";

const ForwardedIconComponent = forwardRef(
  ({ name, className, iconColor }: IconComponentProps, ref) => {
    const TargetIcon = nodeIconsLucide[name] ?? nodeIconsLucide["unknown"];
    return (
      <TargetIcon
        strokeWidth={1.5}
        className={className}
        style={iconColor ? { color: iconColor } : {}}
        ref={ref}
      />
    );
  }
);

export default ForwardedIconComponent;
