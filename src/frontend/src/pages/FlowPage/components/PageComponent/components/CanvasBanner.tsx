import { type HTMLAttributes, type ReactNode } from "react";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Badge } from "@/components/ui/badge";
import { Button, type ButtonProps } from "@/components/ui/button";

export function CanvasBannerButton(props: ButtonProps) {
  return <Button {...props} />;
}

const canvasBadgeVariants = {
  readme:
    "pointer-events-auto absolute left-4 top-4 flex items-center gap-2 whitespace-nowrap rounded-md border border-border bg-background px-3 py-2 text-sm font-medium text-foreground shadow-sm",
} as const;

type CanvasBadgeVariant = keyof typeof canvasBadgeVariants;

interface CanvasBadgeProps extends HTMLAttributes<HTMLDivElement> {
  variant?: CanvasBadgeVariant;
}

export function CanvasBadge({
  variant = "readme",
  className,
  ...props
}: CanvasBadgeProps) {
  return (
    <Badge
      variant="outline"
      className={
        canvasBadgeVariants[variant] + (className ? ` ${className}` : "")
      }
      {...props}
    />
  );
}

const canvasBannerVariants = {
  readme:
    "version-preview-banner flex items-center gap-4 overflow-hidden rounded-xl border border-border bg-background px-5 py-3",
} as const;

type CanvasBannerVariant = keyof typeof canvasBannerVariants;

interface CanvasBannerProps {
  icon: string;
  title: string;
  description: ReactNode;
  actionSlot: ReactNode;
  variant?: CanvasBannerVariant;
}

export default function CanvasBanner({
  icon,
  title,
  description,
  actionSlot,
  variant = "readme",
}: CanvasBannerProps) {
  return (
    <div className="version-preview-banner-enter pointer-events-auto absolute bottom-7 left-1/2 w-[650px]">
      <div className={canvasBannerVariants[variant]}>
        <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-[#6366F1]/20">
          <ForwardedIconComponent
            name={icon}
            className="h-5 w-5 text-[#6366F1]"
          />
        </div>
        <div className="flex flex-1 flex-col">
          <p className="text-foreground text-sm">{title}</p>
          <p className="text-[13px] text-muted-foreground">{description}</p>
        </div>
        <div className="ml-auto flex items-center">{actionSlot}</div>
      </div>
    </div>
  );
}
