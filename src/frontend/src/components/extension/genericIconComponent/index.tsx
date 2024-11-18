import dynamicIconImports from "lucide-react/dynamicIconImports";
import { Suspense, forwardRef, lazy, memo } from "react";
import { IconComponentProps } from "../../../types/components";
import { nodeIconsLucide } from "../../../utils/styleUtils";
import { cn } from "../../../utils/utils";
import Loading from "../../ui/loading";

import { useEffect, useState } from "react";

export const ForwardedIconComponent = memo(
  forwardRef(
    (
      {
        name,
        className,
        iconColor,
        stroke,
        strokeWidth,
        id = "",
        skipFallback = false,
        dataTestId = "",
      }: IconComponentProps,
      ref,
    ) => {
      const [showFallback, setShowFallback] = useState(false);

      useEffect(() => {
        const timer = setTimeout(() => {
          setShowFallback(true);
        }, 30);

        return () => clearTimeout(timer);
      }, []);

      let TargetIcon =
        nodeIconsLucide[name] ||
        nodeIconsLucide[
          name
            ?.split("-")
            ?.map((x) => String(x[0]).toUpperCase() + String(x).slice(1))
            ?.join("")
        ];
      if (!TargetIcon) {
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

      const fallback = showFallback ? (
        <div className={cn(className, "flex items-center justify-center")}>
          <Loading />
        </div>
      ) : (
        <div className={className}></div>
      );

      return (
        <Suspense fallback={skipFallback ? undefined : fallback}>
          <TargetIcon
            className={className}
            style={style}
            ref={ref}
            data-testid={
              dataTestId ? dataTestId : id ? `${id}-${name}` : `icon-${name}`
            }
          />
        </Suspense>
      );
    },
  ),
);

export default ForwardedIconComponent;
