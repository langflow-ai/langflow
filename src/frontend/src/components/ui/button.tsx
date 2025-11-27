import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";
import * as React from "react";
import { cn } from "../../utils/utils";
import ForwardedIconComponent from "../common/genericIconComponent";

const buttonVariants = cva(
  "noflow nopan nodelete nodrag inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-[4px] text-sm font-medium cursor-pointer transition-colors disabled:opacity-70 disabled:pointer-events-none [&_svg]:pointer-events-none [&_svg]:size-4 [&_svg]:shrink-0",
  {
    variants: {
      variant: {
        default: "bg-primary hover:bg-secondary text-white",
        // destructive:
        //   "bg-destructive text-destructive-foreground hover:bg-destructive/90",
        outline:
          "bg-background-surface hover:bg-accent border border-accent text-primary-font",
        icon: "bg-white/10 hover:bg-white/50 text-white rounded-full",
        // outlineAmber:
        //   "border border-accent-amber-foreground hover:bg-accent-amber",
        // primary:
        //   "border bg-background text-secondary-foreground hover:bg-muted hover:shadow-sm",
        // warning:
        //   "bg-warning-foreground text-warning-text hover:bg-warning-foreground/90 hover:shadow-sm",
        // secondary:
        //   "border border-muted bg-muted text-secondary-foreground hover:bg-secondary-foreground/5",
        ghost: "text-secondary-font border border-accent !font-normal",
        // ghostActive:
        //   "bg-muted text-foreground hover:bg-secondary-hover hover:text-accent-foreground",
        // menu: "hover:bg-muted hover:text-accent-foreground focus:!ring-0 focus-visible:!ring-0",
        // "menu-active":
        //   "font-semibold hover:bg-muted hover:text-accent-foreground focus-visible:!ring-offset-0",
        link: "text-link font-medium",
        error: "text-error font-medium border border-error hover:bg-error-bg",
      },
      size: {
        default: "h-10 py-2 px-4",
        xs: "py-0.5 px-3",
        sm: "h-9 px-3",
        md: "h-8 py-2 px-4",
        lg: "h-[38px] text-sm px-4",
        icon: "p-1",
        iconSm: "p-0.5",
        iconMd: "p-1..5",
        "node-toolbar": "py-[6px] px-[6px]",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "default",
    },
  }
);

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean;
  loading?: boolean;
  unstyled?: boolean;
  ignoreTitleCase?: boolean;
}

function toTitleCase(text: string) {
  return text
    ?.split(" ")
    ?.map(
      (word) => word?.charAt(0)?.toUpperCase() + word?.slice(1)?.toLowerCase()
    )
    ?.join(" ");
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
      ...props
    },
    ref
  ) => {
    const Comp = asChild ? Slot : "button";
    let newChildren = children;
    if (typeof children === "string") {
      newChildren = ignoreTitleCase ? children : toTitleCase(children);
    }
    return (
      <>
        <Comp
          className={
            !unstyled
              ? buttonVariants({ variant, size, className })
              : cn(className)
          }
          disabled={loading || disabled}
          {...(asChild ? {} : { type: type || "button" })}
          ref={ref}
          {...props}
        >
          {loading ? (
            <span className="relative flex items-center justify-center">
              <span
                className={cn(
                  className,
                  "invisible flex items-center justify-center gap-2 !p-0"
                )}
              >
                {newChildren}
              </span>
              <span className="absolute inset-0 flex items-center justify-center">
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
  }
);
Button.displayName = "Button";

export { Button, buttonVariants };
