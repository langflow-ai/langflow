import { cva, type VariantProps } from "class-variance-authority";
import type * as React from "react";
import { cn } from "../../utils/utils";

const badgeVariants = cva(
  "inline-flex items-center border rounded-full px-2.5 font-semibold transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2",
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
        purpleStatic:
          "border border-accent-purple-foreground bg-background text-accent-purple-foreground",
        emerald:
          "bg-accent-emerald text-accent-emerald-foreground hover:bg-accent-emerald-hover border-0",
        successStatic:
          "bg-accent-emerald text-accent-emerald-foreground border-0",
        errorStatic: "bg-error-background text-error-foreground border-0",
        // The three change kinds in the version-conflict dialog. Their palette
        // comes from the Enterprise design file rather than the app's accent
        // tokens, which sit on different hues — indigo against purple, and a
        // tinted fill behind each rather than a solid one.
        conflictAdded:
          "border-accent-emerald-foreground/30 bg-accent-emerald-foreground/15 text-accent-emerald-foreground",
        conflictModified:
          "border-accent-indigo-foreground/30 bg-accent-indigo-foreground/15 text-accent-indigo-foreground",
        conflictContested:
          "border-accent-amber-foreground/40 bg-accent-amber-foreground/15 text-accent-amber-foreground",
        conflictRemoved:
          "border-accent-red-foreground/30 bg-accent-red-foreground/15 text-accent-red-foreground",
      },
      size: {
        sm: "h-4 text-xs",
        md: "h-5 text-sm",
        lg: "h-6 text-base",
        sq: "h-6 px-1.5 text-sm font-medium rounded-md",
        xq: "h-6 px-1.5 text-xs font-medium rounded-sm",
        tag: "h-[18px] px-1.5 text-[11px] leading-[14px] font-medium rounded",
        /** The dialog's change badges: 10px semibold in a 4px-radius chip. */
        change:
          "h-[19px] px-1.5 py-0.5 text-[10px] leading-[15px] font-semibold rounded-sm",
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
