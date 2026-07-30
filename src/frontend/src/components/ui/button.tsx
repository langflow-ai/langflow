import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";
import * as React from "react";
import { cn } from "../../utils/utils";
import ForwardedIconComponent from "../common/genericIconComponent";

const buttonVariants = cva(
  "noflow nopan nodelete nodrag inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-md text-sm font-medium ring-offset-background transition-all focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:opacity-70 disabled:pointer-events-none aria-disabled:opacity-70 aria-disabled:pointer-events-none [&_svg]:pointer-events-none [&_svg]:size-4 [&_svg]:shrink-0",
  {
    variants: {
      variant: {
        default: "bg-primary text-primary-foreground  hover:bg-primary-hover",
        destructive:
          "bg-destructive text-destructive-foreground hover:bg-destructive/90",
        outline:
          "border border-input hover:bg-input hover:text-accent-foreground ",
        outlineAmber:
          "border border-accent-amber-foreground hover:bg-accent-amber",
        primary:
          "border bg-background text-secondary-foreground hover:bg-muted hover:shadow-sm",
        warning:
          "bg-warning-foreground text-warning-text hover:bg-warning-foreground/90 hover:shadow-sm",
        secondary:
          "border border-muted bg-muted text-secondary-foreground hover:bg-secondary-foreground/5",
        ghost:
          "text-foreground hover:bg-accent hover:text-accent-foreground disabled:!bg-transparent",
        ghostActive:
          "bg-muted text-foreground hover:bg-secondary-hover hover:text-accent-foreground",
        menu: "hover:bg-muted hover:text-accent-foreground focus:!ring-0 focus-visible:!ring-0",
        "menu-active":
          "font-semibold hover:bg-muted hover:text-accent-foreground focus-visible:!ring-offset-0",
        link: "underline-offset-4 hover:underline text-primary",
      },
      size: {
        default: "h-10 py-2 px-4",
        md: "h-8 py-2 px-4",
        sm: "h-9 px-3 rounded-md",
        xs: "py-0.5 px-3 rounded-md",
        lg: "h-11 px-8 rounded-md",
        iconMd: "p-1.5 rounded-md",
        icon: "p-1 rounded-md",
        iconSm: "p-0.5 rounded-md",
        "node-toolbar": "py-[6px] px-[6px] rounded-md",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "default",
    },
  },
);

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean;
  loading?: boolean;
  unstyled?: boolean;
  ignoreTitleCase?: boolean;
  shouldScale?: boolean;
}

function toTitleCase(text: string) {
  return text
    ?.split(" ")
    ?.map(
      (word) => word?.charAt(0)?.toUpperCase() + word?.slice(1)?.toLowerCase(),
    )
    ?.join(" ");
}

function assignRef<T>(ref: React.Ref<T> | undefined, value: T | null) {
  if (!ref) return;
  if (typeof ref === "function") {
    ref(value);
    return;
  }
  (ref as React.MutableRefObject<T | null>).current = value;
}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  (
    {
      className,
      variant,
      unstyled,
      size,
      loading,
      type,
      disabled,
      asChild = false,
      children,
      ignoreTitleCase = false,
      shouldScale = true,
      onClick,
      onKeyDown,
      ...props
    },
    ref,
  ) => {
    // ElementType avoids Slot|"button" intersecting child props with i18n's
    // ReactI18NextChildren (Record<string, unknown>), which breaks the loading branch.
    const Comp: React.ElementType = asChild ? Slot : "button";
    let newChildren: React.ReactNode = children as React.ReactNode;
    if (typeof children === "string") {
      newChildren = ignoreTitleCase ? children : toTitleCase(children);
    }
    const shouldScaleButton =
      props["aria-haspopup"] !== "dialog" || shouldScale;
    // Native `disabled` drops focus to <body>. While loading, keep the control
    // focusable with aria-disabled so keyboard users retain place and aria-busy
    // can be announced on the focused element (WCAG 2.4.3 / 4.1.2).
    // Call sites often pass `disabled={… || isLoading}` alongside `loading` —
    // loading wins so focus is retained even when those props overlap.
    const isBusy = Boolean(loading);
    const blockActivation = Boolean(disabled) || isBusy;
    const nativeDisabled = Boolean(disabled) && !isBusy;

    const localRef = React.useRef<HTMLButtonElement | null>(null);
    const retainFocusRef = React.useRef(false);

    const setRefs = React.useCallback(
      (node: HTMLButtonElement | null) => {
        localRef.current = node;
        assignRef(ref, node);
      },
      [ref],
    );

    const markRetainFocus = () => {
      retainFocusRef.current = true;
    };

    const handleClick = (event: React.MouseEvent<HTMLButtonElement>) => {
      if (blockActivation) {
        event.preventDefault();
        return;
      }
      markRetainFocus();
      onClick?.(event);
    };

    const handleKeyDown = (event: React.KeyboardEvent<HTMLButtonElement>) => {
      if (
        blockActivation &&
        (event.key === "Enter" || event.key === " " || event.key === "Spacebar")
      ) {
        event.preventDefault();
        return;
      }
      if (
        event.key === "Enter" ||
        event.key === " " ||
        event.key === "Spacebar"
      ) {
        markRetainFocus();
      }
      onKeyDown?.(event);
    };

    // Re-assert focus across busy transitions. Child swaps (spinner) or
    // overlapping disabled props can still drop focus even with aria-disabled.
    React.useLayoutEffect(() => {
      if (!retainFocusRef.current) return;
      const node = localRef.current;
      if (!node) return;

      if (isBusy) {
        if (document.activeElement !== node) {
          node.focus({ preventScroll: true });
        }
        return;
      }

      if (
        document.activeElement === document.body ||
        document.activeElement === null
      ) {
        node.focus({ preventScroll: true });
      }
      retainFocusRef.current = false;
    }, [isBusy]);

    return (
      <>
        <Comp
          className={
            !unstyled
              ? cn(
                  buttonVariants({ variant, size, className }),
                  shouldScaleButton && "active:scale-[0.97]",
                )
              : cn(className)
          }
          {...(asChild ? {} : { type: type || "button" })}
          ref={setRefs}
          {...props}
          disabled={nativeDisabled || undefined}
          aria-disabled={isBusy || undefined}
          aria-busy={isBusy || undefined}
          onClick={handleClick}
          onKeyDown={handleKeyDown}
        >
          {loading ? (
            <span className="relative flex items-center justify-center">
              {/* Reserve layout width; hide from a11y so the name comes from sr-only. */}
              <span
                aria-hidden="true"
                className={cn(
                  className,
                  "invisible flex items-center justify-center gap-2 !p-0",
                )}
              >
                {newChildren}
              </span>
              <span className="sr-only">{newChildren}</span>
              <span
                aria-hidden="true"
                className="absolute inset-0 flex items-center justify-center"
              >
                <ForwardedIconComponent
                  name={"Loader2"}
                  className={"h-full w-full animate-spin"}
                />
              </span>
            </span>
          ) : (
            newChildren
          )}
        </Comp>
      </>
    );
  },
);
Button.displayName = "Button";

export { Button, buttonVariants };
