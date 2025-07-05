import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";
import * as React from "react";
import { cn } from "../../utils/utils";
import ForwardedIconComponent from "../common/genericIconComponent";

const buttonVariants = cva(
  "noflow nopan nodelete nodrag inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-md text-sm font-medium ring-offset-background transition-colors focus-visible:outline-hidden focus-visible:ring-1 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:opacity-70 disabled:pointer-events-none [&_svg]:pointer-events-none [&_svg]:size-4 [&_svg]:shrink-0",
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
          "border bg-background text-secondary-foreground hover:bg-muted hover:shadow-2xs",
        warning:
          "bg-warning-foreground text-warning-text hover:bg-warning-foreground/90 hover:shadow-2xs",
        secondary:
          "border border-muted bg-muted text-secondary-foreground hover:bg-secondary-foreground/5",
        ghost:
          "text-foreground hover:bg-accent hover:text-accent-foreground disabled:bg-transparent!",
        ghostActive:
          "bg-muted text-foreground hover:bg-secondary-hover hover:text-accent-foreground",
        menu: "hover:bg-muted hover:text-accent-foreground focus:ring-0! focus-visible:ring-0!",
        "menu-active":
          "font-semibold hover:bg-muted hover:text-accent-foreground focus-visible:ring-offset-0!",
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
}

function toTitleCase(text: string) {
  return text
    ?.split(" ")
    ?.map(
      (word) => word?.charAt(0)?.toUpperCase() + word?.slice(1)?.toLowerCase(),
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
    ref,
  ) => {
    const Comp = asChild ? Slot : "button";
    let newChildren = children;
    if (typeof children === "string") {
      newChildren = ignoreTitleCase ? children : toTitleCase(children);
    }

    return (
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
                "invisible flex items-center justify-center gap-2 p-0!",
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
    );
  },
);
Button.displayName = "Button";

export { Button, buttonVariants };
