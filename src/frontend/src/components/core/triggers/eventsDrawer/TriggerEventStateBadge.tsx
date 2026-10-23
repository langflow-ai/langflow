import { useTranslation } from "react-i18next";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Badge } from "@/components/ui/badge";
import type { TriggerEventRead } from "@/controllers/API/queries/triggers";
import { cn } from "@/utils/utils";
import {
  eventDisplayStateOf,
  type TriggerEventDisplayState,
} from "../helpers/trigger-presentation";

const STYLE: Record<
  TriggerEventDisplayState,
  { icon: string; className: string }
> = {
  queued: { icon: "Clock", className: "bg-muted text-muted-foreground" },
  running: {
    icon: "LoaderCircle",
    className: "bg-accent-indigo text-accent-indigo-foreground",
  },
  completed: {
    icon: "CircleCheck",
    className: "bg-accent-emerald text-accent-emerald-foreground",
  },
  failed: {
    icon: "CircleX",
    className: "bg-error-background text-error-foreground",
  },
  dead: {
    icon: "Archive",
    className: "bg-error-background text-error-foreground",
  },
};

export function TriggerEventStateBadge({
  event,
}: {
  event: Pick<TriggerEventRead, "state">;
}) {
  const { t } = useTranslation();
  const state = eventDisplayStateOf(event);
  const style = STYLE[state];
  return (
    <Badge
      variant="outline"
      size="xq"
      className={cn("w-fit gap-1 border-0", style.className)}
      data-testid="trigger-event-state"
      data-state={event.state}
    >
      <ForwardedIconComponent
        name={style.icon}
        aria-hidden="true"
        className={cn(
          "h-3 w-3",
          state === "running" && "motion-safe:animate-spin",
        )}
      />
      {t(`triggers.events.state.${state}`)}
    </Badge>
  );
}

export default TriggerEventStateBadge;
