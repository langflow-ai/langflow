import { forwardRef } from "react";
import { IconComponentProps } from "../../types/components";
import { nodeIconsLucide } from "../../utils/styleUtils";

const ForwardedIconComponent = forwardRef(
  (
    {
      name,
      className,
      iconColor,
      stroke,
      strokeWidth,
      id = "",
    }: IconComponentProps,
    ref
  ) => {
    const TargetIcon = nodeIconsLucide[name] ?? nodeIconsLucide["unknown"];

    const style = {
      strokeWidth: strokeWidth ?? 1.5,
      ...(stroke && { stroke: stroke }),
      ...(iconColor && { color: iconColor, stroke: stroke }),
    };

    return (
      <TargetIcon
        className={className}
        style={style}
        ref={ref}
        data-testid={id ? `${id}-${name}` : `icon-${name}`}
      />
    );
  }
);

export default ForwardedIconComponent;
