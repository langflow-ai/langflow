import { cva, type VariantProps } from "class-variance-authority";
import type * as React from "react";
import { cn } from "../../utils/utils";

const badgeVariants = cva(
  "inline-flex items-center rounded-full py-[3px] px-2 font-medium transition-colors",
  {
    variants: {
      variant: {
        default: "bg-primary hover:bg-primary/80 border-transparent text-white",
        gray: "bg-border hover:bg-border/80 text-secondary-foreground",
        secondary: "bg-secondary text-white",
        destructive:
          "bg-destructive hover:bg-destructive/80 border-transparent text-destructive-foreground",
        outline: "text-primary/80 border-ring/60",
        secondaryStatic: "bg-accent-light text-secondary-font border-0",
        pinkStatic: "bg-accent-pink text-accent-pink-foreground border-0",
        emerald:
          "bg-accent-emerald text-accent-emerald-foreground hover:bg-accent-emerald-hover border-0",
        successStatic:
          "bg-accent-emerald text-accent-emerald-foreground border-0",
        errorStatic: "bg-error-background text-error-foreground border-0",
      },
      size: {
        sm: "text-xs",
        md: "h-5 text-sm",
        lg: "h-6 text-base",
        sq: "h-6 px-1.5 text-sm font-medium rounded-md",
        xq: "h-6 px-1.5 text-xs font-medium rounded-sm",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "sm",
    },
  }
);

export interface BadgeProps
  extends React.HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof badgeVariants> {}

function Badge({ className, variant, size, ...props }: BadgeProps) {
  return (
    <div
      className={cn(badgeVariants({ variant, size }), className)}
      {...props}
    />
  );
}

export { Badge, badgeVariants };
