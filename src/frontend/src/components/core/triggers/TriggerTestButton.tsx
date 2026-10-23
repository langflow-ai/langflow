import { useId } from "react";
import { useTranslation } from "react-i18next";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import ShadTooltip from "@/components/common/shadTooltipComponent";
import { Button } from "@/components/ui/button";
import type { TriggerRead } from "@/controllers/API/queries/triggers";
import {
  availabilityOf,
  blockedReasonKey,
} from "./helpers/trigger-presentation";

export interface TriggerTestButtonProps {
  trigger: TriggerRead;
  busy: boolean;
  onTest: (trigger: TriggerRead) => void;
}

/** Icon Test button; rendered only when test applies to this trigger. */
export function TriggerTestButton({
  trigger,
  busy,
  onTest,
}: TriggerTestButtonProps) {
  const { t } = useTranslation();
  const reasonId = useId();
  const availability = availabilityOf(trigger, "test");
  if (!availability) return null;
  const { blockedReason } = availability;
  const tooltip = blockedReason
    ? t(blockedReasonKey(blockedReason))
    : t("triggers.actions.test");
  return (
    <ShadTooltip content={tooltip}>
      <Button
        variant="ghost"
        size="iconMd"
        aria-label={t("triggers.actions.testAria", { name: trigger.name })}
        aria-disabled={blockedReason ? true : undefined}
        aria-describedby={blockedReason ? reasonId : undefined}
        disabled={busy}
        className={
          blockedReason
            ? "cursor-not-allowed opacity-50 aria-disabled:pointer-events-auto"
            : undefined
        }
        onClick={() => {
          if (!blockedReason) onTest(trigger);
        }}
        data-testid={`trigger-test-${trigger.id}`}
      >
        <ForwardedIconComponent
          name="Send"
          aria-hidden="true"
          className="h-4 w-4"
        />
        {blockedReason && (
          <span id={reasonId} className="sr-only">
            {tooltip}
          </span>
        )}
      </Button>
    </ShadTooltip>
  );
}

export default TriggerTestButton;
