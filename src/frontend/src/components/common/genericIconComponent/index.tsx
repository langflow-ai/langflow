import React, {
  forwardRef,
  memo,
  Suspense,
  useCallback,
  useEffect,
  useState,
} from "react";
import { Skeleton } from "@/components/ui/skeleton";
import { useDarkStore } from "../../../stores/darkStore";
import { IconComponentProps } from "../../../types/components";
import { getCachedIcon, getNodeIcon } from "../../../utils/styleUtils";
import { cn } from "../../../utils/utils";

type IconComponentType = React.ComponentType<{
  className?: string;
  style?: React.CSSProperties;
  ref?: React.Ref<unknown>;
  "data-testid"?: string;
  isDark?: boolean;
}>;

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
      // Subscribe to dark store directly in memoized component
      // This forces re-render when theme changes, bypassing memo
      const { dark: isDark } = useDarkStore();

      const [showFallback, setShowFallback] = useState(false);
      const [iconError, setIconError] = useState(false);
      const [TargetIcon, setTargetIcon] = useState<IconComponentType | null>(
        getCachedIcon(name) as IconComponentType | null,
      );

      useEffect(() => {
        setIconError(false);
        setTargetIcon(null);
        setShowFallback(false);

        let isMounted = true;
        let timer: NodeJS.Timeout | null = null;

        if (name && typeof name === "string") {
          getNodeIcon(name)
            .then((component) => {
              if (isMounted) {
                setTargetIcon(component);
                setShowFallback(false);
              }
            })
            .catch((error) => {
              if (isMounted) {
                console.error(`Error loading icon ${name}:`, error);
                setIconError(true);
                setShowFallback(false);
              }
            });

          // Show fallback skeleton if icon takes too long
          timer = setTimeout(() => {
            if (isMounted) setShowFallback(true);
          }, 30);
        }

        return () => {
          isMounted = false;
          if (timer) clearTimeout(timer);
        };
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

      // Check if TargetIcon is a valid React component (function, class, or lazy component)
      // In React 19, lazy components have $$typeof Symbol, and forwardRef components have render property
      const isValidComponent =
        typeof TargetIcon === "function" ||
        (typeof TargetIcon === "object" &&
          TargetIcon !== null &&
          (() => {
            const targetIconObj = TargetIcon as {
              $$typeof?: unknown;
              render?: unknown;
              _payload?: unknown;
              type?: unknown;
            };
            return (
              targetIconObj.$$typeof ||
              targetIconObj.render ||
              targetIconObj._payload ||
              targetIconObj.type
            );
          })());
      // Check for various React component types:
      // - $$typeof: lazy, forwardRef, memo components (Symbol.for('react.lazy'), etc.)
      // - render: forwardRef components in some React versions
      // - _payload: lazy component internals
      // - type: wrapped components (memo wrapping forwardRef))

      const baseProps = {
        className,
        style,
        "data-testid": dataTestId
          ? dataTestId
          : id
            ? `${id}-${name}`
            : `icon-${name}`,
      };

      const componentProps = { ...baseProps, ref };

      const content = isValidComponent ? (
        <TargetIcon {...componentProps} isDark={isDark} />
      ) : (
        <div {...baseProps}>{TargetIcon}</div>
      );

      return (
        <Suspense fallback={skipFallback ? undefined : fallback}>
          <ErrorBoundary onError={handleError}>{content}</ErrorBoundary>
        </Suspense>
      );
    },
  ),
);

// Simple error boundary component for catching lazy load errors
class ErrorBoundary extends React.Component<
  {
    children: React.ReactNode;
    onError: () => void;
  },
  { hasError: boolean }
> {
  constructor(props: { children: React.ReactNode; onError: () => void }) {
    super(props);
    this.state = { hasError: false };
  }

  static getDerivedStateFromError(_error: Error) {
    return { hasError: true };
  }

  componentDidCatch(error: Error) {
    this.props.onError();
  }

  render() {
    if (this.state.hasError) {
      return null;
    }
    return this.props.children;
  }
}

export default ForwardedIconComponent;
