import dynamicIconImports from "lucide-react/dynamicIconImports";
import { Suspense, forwardRef, lazy, memo } from "react";
import { IconComponentProps } from "../../types/components";
import { nodeIconsLucide } from "../../utils/styleUtils";

const ForwardedIconComponent = memo(
  forwardRef(
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
      let TargetIcon = nodeIconsLucide[name];
      if (!TargetIcon) {
        // check if name exists in dynamicIconImports
        if (!dynamicIconImports[name]) {
          TargetIcon = nodeIconsLucide["unknown"];
        } else TargetIcon = lazy(dynamicIconImports[name]);
      }

      const style = {
        strokeWidth: strokeWidth ?? 1.5,
        ...(stroke && { stroke: stroke }),
        ...(iconColor && { color: iconColor, stroke: stroke }),
      };

      if (!TargetIcon) {
        return null; // Render nothing until the icon is loaded
      }
      const fallback = (
        <div style={{ background: "#ddd", width: 24, height: 24 }} />
      );
      return (
        <Suspense fallback={fallback}>
          <TargetIcon
            className={className}
            style={style}
            ref={ref}
            data-testid={id ? `${id}-${name}` : `icon-${name}`}
          />
        </Suspense>
      );
    }
  )
);

export default ForwardedIconComponent;
