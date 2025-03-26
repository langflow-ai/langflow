import dynamicIconImports from "lucide-react/dynamicIconImports";
import React, { Suspense, forwardRef, lazy, memo } from "react";
import { IconComponentProps } from "../../../types/components";
import { getNodeIcon } from "../../../utils/styleUtils";
import { cn } from "../../../utils/utils";
import Loading from "../../ui/loading";

import { useCallback, useEffect, useState } from "react";
import { Skeleton } from "@/components/ui/skeleton";

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
      const [iconError, setIconError] = useState(false);

      useEffect(() => {
        // Reset error state when icon name changes
        setIconError(false);

        const timer = setTimeout(() => {
          setShowFallback(true);
        }, 30);

        return () => clearTimeout(timer);
      }, [name]);

      // Get the lazy-loaded icon component
      let TargetIcon;

      // Only try to load an icon if we have a name
      if (name && typeof name === "string") {
        try {
          TargetIcon = getNodeIcon(name);
        } catch (error) {
          console.error(`Error loading icon ${name}:`, error);
          setIconError(true);
        }
      }

      const style = {
        strokeWidth: strokeWidth ?? 1.5,
        ...(stroke && { stroke: stroke }),
        ...(iconColor && { color: iconColor, stroke: stroke }),
      };

      // Handler for when the Suspense component throws
      const handleError = useCallback(() => {
        setIconError(true);
      }, []);

      if (!TargetIcon || iconError) {
        // Return a placeholder div or null depending on settings
        return skipFallback ? null : (
          <div
            className={cn(className, "flex items-center justify-center")}
            data-testid={
              dataTestId
                ? dataTestId
                : id
                  ? `${id}-placeholder`
                  : `icon-placeholder`
            }
          />
        );
      }

      const fallback = showFallback ? (
        <div className={cn(className, "flex items-center justify-center")}>
          {/* <Loading /> */}
          <Skeleton className="h-4 w-4" />
        </div>
      ) : (
        <div className={className}></div>
      );

      return (
        <Suspense fallback={skipFallback ? undefined : fallback}>
          <ErrorBoundary onError={handleError}>
            <TargetIcon
              className={className}
              style={style}
              ref={ref}
              data-testid={
                dataTestId ? dataTestId : id ? `${id}-${name}` : `icon-${name}`
              }
            />
          </ErrorBoundary>
        </Suspense>
      );
    },
  ),
);

// Simple error boundary component for catching lazy load errors
class ErrorBoundary extends React.Component<{
  children: React.ReactNode;
  onError: () => void;
}> {
  componentDidCatch(error: any) {
    this.props.onError();
  }

  render() {
    return this.props.children;
  }
}

export default ForwardedIconComponent;
