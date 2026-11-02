import { useId } from "react";
import { useTranslation } from "react-i18next";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import ShadTooltip from "@/components/common/shadTooltipComponent";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import type {
  TriggerAction,
  TriggerRead,
  TriggerReason,
} from "@/controllers/API/queries/triggers";
import { cn } from "@/utils/utils";
import {
  actionLabelKey,
  actionsOf,
  blockedReasonKey,
} from "./helpers/trigger-presentation";
import type { TriggerUiAction } from "./hooks/use-trigger-action-runner";

const ACTION_ICON: Record<TriggerUiAction, string> = {
  view_events: "List",
  open_flow: "ExternalLink",
  pause: "Pause",
  resume: "Play",
  test: "Send",
  reconnect: "RefreshCw",
  replay: "RotateCcw",
  rotate_secret: "KeyRound",
  delete: "Trash2",
};

/** Menu-worthy server actions; test has its own button and replay its drawer. */
const MENU_ACTIONS: readonly TriggerAction[] = [
  "pause",
  "resume",
  "reconnect",
  "rotate_secret",
];

export interface TriggerActionMenuProps {
  trigger: TriggerRead;
  busy: boolean;
  onAction: (trigger: TriggerRead, action: TriggerUiAction) => void;
  /** Hidden when the caller is already on the flow. */
  showOpenFlow?: boolean;
}

function MenuAction({
  action,
  blockedReason,
  destructive,
  onSelect,
}: {
  action: TriggerUiAction;
  blockedReason?: TriggerReason;
  destructive?: boolean;
  onSelect: () => void;
}) {
  const { t } = useTranslation();
  const reasonId = useId();
  const blocked = blockedReason !== undefined;
  const label =
    action === "view_events" || action === "open_flow"
      ? t(`triggers.actions.${action}`)
      : t(actionLabelKey(action));
  const item = (
    <DropdownMenuItem
      // A blocked action stays focusable so its reason reaches keyboard and
      // screen-reader users; selecting it does nothing.
      aria-disabled={blocked || undefined}
      aria-describedby={blocked ? reasonId : undefined}
      onSelect={(event) => {
        if (blocked) {
          event.preventDefault();
          return;
        }
        onSelect();
      }}
      className={cn(
        destructive && !blocked && "text-destructive focus:text-destructive",
        blocked && "cursor-not-allowed text-muted-foreground opacity-60",
      )}
      data-testid={`trigger-action-${action}`}
    >
      <ForwardedIconComponent
        name={ACTION_ICON[action]}
        aria-hidden="true"
        className="mr-2 h-4 w-4"
      />
      {label}
      {blocked && (
        <span id={reasonId} className="sr-only">
          {t(blockedReasonKey(blockedReason))}
        </span>
      )}
    </DropdownMenuItem>
  );
  return blocked ? (
    <ShadTooltip content={t(blockedReasonKey(blockedReason))} side="left">
      {item}
    </ShadTooltip>
  ) : (
    item
  );
}

/** Row menu: unavailable actions stay visible and explain themselves. */
export function TriggerActionMenu({
  trigger,
  busy,
  onAction,
  showOpenFlow = true,
}: TriggerActionMenuProps) {
  const { t } = useTranslation();
  const serverActions = actionsOf(trigger, MENU_ACTIONS);
  const deletion = actionsOf(trigger, ["delete"])[0];

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button
          variant="ghost"
          size="iconMd"
          disabled={busy}
          aria-label={t("triggers.actions.menu", { name: trigger.name })}
          data-testid={`trigger-menu-${trigger.id}`}
        >
          <ForwardedIconComponent
            name="Ellipsis"
            aria-hidden="true"
            className="h-4 w-4"
          />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="min-w-[14rem]">
        <MenuAction
          action="view_events"
          onSelect={() => onAction(trigger, "view_events")}
        />
        {showOpenFlow && (
          <MenuAction
            action="open_flow"
            onSelect={() => onAction(trigger, "open_flow")}
          />
        )}
        {serverActions.map(({ action, blockedReason }) => (
          <MenuAction
            key={action}
            action={action}
            blockedReason={blockedReason}
            onSelect={() => onAction(trigger, action)}
          />
        ))}
        {deletion && (
          <>
            <DropdownMenuSeparator />
            <MenuAction
              action="delete"
              destructive
              blockedReason={deletion.blockedReason}
              onSelect={() => onAction(trigger, "delete")}
            />
          </>
        )}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

export default TriggerActionMenu;
