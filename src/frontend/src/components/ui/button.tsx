import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";
import * as React from "react";
import { cn } from "../../utils/utils";
import ForwardedIconComponent from "../genericIconComponent";

const buttonVariants = cva(
  "noflow nowheel nopan nodelete nodrag  inline-flex items-center gap-2 justify-center rounded-md text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:opacity-50 disabled:pointer-events-none  ring-offset-background",
  {
    variants: {
      variant: {
        default: "bg-primary text-primary-foreground hover:bg-primary/90",
        destructive:
          "bg-destructive text-destructive-foreground hover:bg-destructive/90",
        outline:
          "border border-input hover:bg-input hover:text-accent-foreground",
        primary:
          "border bg-background text-secondary-foreground hover:bg-secondary-foreground/5 dark:hover:bg-background/10 hover:shadow-sm",
        secondary:
          "border border-muted bg-muted text-secondary-foreground hover:bg-secondary-foreground/5",
        ghost: "hover:bg-accent hover:text-accent-foreground",
        link: "underline-offset-4 hover:underline text-primary",
      },
      size: {
        default: "h-10 py-2 px-4",
        sm: "h-9 px-3 rounded-md",
        xs: "py-0.5 px-3 rounded-md",
        lg: "h-11 px-8 rounded-md",
        icon: "py-1 px-1 rounded-md",
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
}

function toTitleCase(text: string) {
  return text
    .split(" ")
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1).toLowerCase())
    .join(" ");
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
      ...props
    },
    ref,
  ) => {
    const Comp = asChild ? Slot : "button";
    let newChildren = children;
    if (typeof children === "string") {
      newChildren = toTitleCase(children);
    }
    return (
      <>
        <Comp
          className={
            !unstyled
              ? buttonVariants({ variant, size, className })
              : cn(className, "noflow nowheel nopan nodelete nodrag")
          }
          disabled={loading || disabled}
          {...(asChild ? {} : { type: type || "button" })}
          ref={ref}
          {...props}
        >
          {loading ? (
            <span className="relative">
              <span className="invisible">{newChildren}</span>
              <span className="absolute inset-0">
                <ForwardedIconComponent
                  name={"Loader2"}
                  className={"m-auto h-full animate-spin"}
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
