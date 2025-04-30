import React, { Suspense, forwardRef, lazy, memo } from "react";
import { IconComponentProps } from "../../../types/components";
import { getNodeIcon } from "../../../utils/styleUtils";
import { cn } from "../../../utils/utils";

import { Skeleton } from "@/components/ui/skeleton";
import { useCallback, useEffect, useState } from "react";

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
      const [initialName, setInitialName] = useState(name);
      const [TargetIcon, setTargetIcon] = useState<any>(null);

      useEffect(() => {
        // Reset states when icon name changes
        if (!TargetIcon || initialName !== name) {
          setInitialName(name);
          setIconError(false);
          setTargetIcon(null);

          const timer = setTimeout(() => {
            setShowFallback(true);
          }, 30);

          // Load the icon if we have a name
          if (name && typeof name === "string") {
            getNodeIcon(name)
              .then((component) => {
                setTargetIcon(component);
                setShowFallback(false);
              })
              .catch((error) => {
                console.error(`Error loading icon ${name}:`, error);
                setIconError(true);
                setShowFallback(false);
              });
          } else {
            setShowFallback(false);
          }

          return () => clearTimeout(timer);
        }
      }, [name]);

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
          <Skeleton className="h-4 w-4" />
        </div>
      ) : (
        <div className={className}></div>
      );

      return (
        <Suspense fallback={skipFallback ? undefined : fallback}>
          <ErrorBoundary onError={handleError}>
            {TargetIcon?.render || TargetIcon?._payload ? (
              <TargetIcon
                className={className}
                style={style}
                ref={ref}
                data-testid={
                  dataTestId
                    ? dataTestId
                    : id
                      ? `${id}-${name}`
                      : `icon-${name}`
                }
              />
            ) : (
              <div
                className={className}
                style={style}
                data-testid={
                  dataTestId
                    ? dataTestId
                    : id
                      ? `${id}-${name}`
                      : `icon-${name}`
                }
              >
                {TargetIcon}
              </div>
            )}
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
