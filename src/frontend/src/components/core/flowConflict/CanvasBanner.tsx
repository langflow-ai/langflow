import type { ReactNode } from "react";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { cn } from "@/utils/utils";

type CanvasBannerProps = {
  icon: string;
  tone: "warning" | "neutral";
  title: string;
  description: string;
  actions: ReactNode;
  testId: string;
};

/**
 * The one shell both canvas banners sit in.
 *
 * They occupy the same slot at the bottom of the canvas and never appear together,
 * so any difference in height, radius or type reads as one of them being wrong.
 */
export function CanvasBanner({
  icon,
  tone,
  title,
  description,
  actions,
  testId,
}: CanvasBannerProps) {
  return (
    <div
      className="pointer-events-none absolute inset-x-0 bottom-6 z-50 flex justify-center px-6"
      data-testid={testId}
    >
      <div
        role="status"
        className="pointer-events-auto flex w-full max-w-[660px] items-start gap-3 rounded-[14px] border border-muted bg-background px-4 py-3.5 shadow-[0_25px_25px_rgba(0,0,0,0.25)]"
      >
        <div
          className={cn(
            "mt-0.5 flex size-9 shrink-0 items-center justify-center rounded-[10px]",
            tone === "warning" ? "bg-accent-amber-foreground/10" : "bg-muted",
          )}
        >
          <ForwardedIconComponent
            name={icon}
            className={cn(
              "h-4 w-4",
              tone === "warning"
                ? "text-accent-amber-foreground"
                : "text-muted-foreground",
            )}
            aria-hidden="true"
          />
        </div>
        <div className="flex min-w-0 flex-1 flex-col gap-1">
          <p className="text-sm font-semibold leading-[21px] text-foreground">
            {title}
          </p>
          <p className="text-xs leading-[18px] text-muted-foreground">
            {description}
          </p>
        </div>
        <div className="mt-0.5 flex h-9 shrink-0 items-center gap-2">
          {actions}
        </div>
      </div>
    </div>
  );
}

export default CanvasBanner;
