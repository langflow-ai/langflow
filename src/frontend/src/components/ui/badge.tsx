import { cva, type VariantProps } from "class-variance-authority";
import type * as React from "react";
import { cn } from "../../utils/utils";

const badgeVariants = cva(
  "inline-flex items-center border rounded-full px-2.5 font-semibold transition-colors focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2",
  {
    variants: {
      variant: {
        default:
          "bg-primary hover:bg-primary/80 border-transparent text-primary-foreground",
        gray: "bg-border hover:bg-border/80 text-secondary-foreground",
        secondary:
          "bg-secondary hover:bg-secondary/80 border-transparent text-secondary-foreground",
        destructive:
          "bg-destructive hover:bg-destructive/80 border-transparent text-destructive-foreground",
        outline: "text-primary/80 border-ring/60",
        secondaryStatic: "bg-muted text-muted-foreground border-0",
        pinkStatic: "bg-accent-pink text-accent-pink-foreground border-0",
        emerald:
          "bg-accent-emerald text-accent-emerald-foreground hover:bg-accent-emerald-hover border-0",
        successStatic:
          "bg-accent-emerald text-accent-emerald-foreground border-0",
        errorStatic: "bg-error-background text-error-foreground border-0",
      },
      size: {
        sm: "h-4 text-xs",
        md: "h-5 text-sm",
        lg: "h-6 text-base",
        sq: "h-6 px-1.5 text-sm font-medium rounded-md",
        xq: "h-6 px-1.5 text-xs font-medium rounded-sm",
      },
    },
    defaultVariants: {
      variant: "default",
    },
  },
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
