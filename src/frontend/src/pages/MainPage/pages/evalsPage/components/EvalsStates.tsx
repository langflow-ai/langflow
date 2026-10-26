import type { ReactNode } from "react";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import {
  Empty,
  EmptyContent,
  EmptyDescription,
  EmptyHeader,
  EmptyTitle,
} from "@/components/ui/empty-state";
import Loading from "@/components/ui/loading";
import { cn } from "@/utils/utils";

interface EvalsEmptyStateProps {
  icon: string;
  title: string;
  description: string;
  actions?: ReactNode;
  testId?: string;
  /** Spin the icon for "waiting" states; it stays still under prefers-reduced-motion. */
  spinning?: boolean;
}

/** Same composition and sizes as the Knowledge and Files empty states. */
export function EvalsEmptyState({
  icon,
  title,
  description,
  actions,
  testId,
  spinning = false,
}: EvalsEmptyStateProps) {
  return (
    <Empty className="h-full w-full gap-8 pb-8" data-testid={testId}>
      <EmptyHeader className="gap-2">
        <ForwardedIconComponent
          name={icon}
          aria-hidden="true"
          className={cn(
            "mb-2 h-8 w-8 text-muted-foreground",
            spinning && "animate-spin motion-reduce:animate-none",
          )}
        />
        <EmptyTitle className="text-2xl">{title}</EmptyTitle>
        <EmptyDescription className="max-w-lg text-center text-lg text-secondary-foreground">
          {description}
        </EmptyDescription>
      </EmptyHeader>
      {actions && <EmptyContent className="gap-2">{actions}</EmptyContent>}
    </Empty>
  );
}

export function EvalsLoadingState({ label }: { label: string }) {
  return (
    <div
      className="flex w-full flex-1 flex-col items-center justify-center gap-3 py-16"
      role="status"
    >
      <Loading size={36} />
      <span className="pt-3 text-sm text-muted-foreground">{label}</span>
    </div>
  );
}
