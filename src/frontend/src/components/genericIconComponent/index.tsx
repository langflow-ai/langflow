import dynamicIconImports from "lucide-react/dynamicIconImports";
import { Suspense, forwardRef, lazy, memo } from "react";
import { IconComponentProps } from "../../types/components";
import { nodeIconsLucide } from "../../utils/styleUtils";
import { cn } from "../../utils/utils";
import Loading from "../ui/loading";

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
        <div className={cn(className, "flex items-center justify-center")}>
          <Loading />
        </div>
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
