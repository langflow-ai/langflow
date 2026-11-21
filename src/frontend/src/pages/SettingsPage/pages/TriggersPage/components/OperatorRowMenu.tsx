import { useTranslation } from "react-i18next";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import type {
  TriggerBulkAction,
  TriggerRead,
} from "@/controllers/API/queries/triggers";

export interface OperatorRowMenuProps {
  trigger: TriggerRead;
  busy: boolean;
  onBulk: (trigger: TriggerRead, action: TriggerBulkAction) => void;
}

/**
 * The operator acts on another user's trigger through the bulk routes, which
 * decide per row whether it is eligible; nothing is derived from state here.
 */
export function OperatorRowMenu({
  trigger,
  busy,
  onBulk,
}: OperatorRowMenuProps) {
  const { t } = useTranslation();
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button
          variant="ghost"
          size="iconMd"
          disabled={busy}
          aria-label={t("triggers.actions.menu", { name: trigger.name })}
          data-testid={`trigger-operator-menu-${trigger.id}`}
        >
          <ForwardedIconComponent
            name="Ellipsis"
            aria-hidden="true"
            className="h-4 w-4"
          />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="min-w-[14rem]">
        <DropdownMenuItem onSelect={() => onBulk(trigger, "pause")}>
          <ForwardedIconComponent
            name="Pause"
            aria-hidden="true"
            className="mr-2 h-4 w-4"
          />
          {t("triggers.operator.pauseOne")}
        </DropdownMenuItem>
        <DropdownMenuItem onSelect={() => onBulk(trigger, "resume")}>
          <ForwardedIconComponent
            name="Play"
            aria-hidden="true"
            className="mr-2 h-4 w-4"
          />
          {t("triggers.operator.resumeOne")}
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

export default OperatorRowMenu;
