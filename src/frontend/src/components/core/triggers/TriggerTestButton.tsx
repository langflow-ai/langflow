import { useTranslation } from "react-i18next";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import type { TriggerRead } from "@/controllers/API/queries/triggers";
import { BlockableButton } from "./BlockableButton";
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
  const availability = availabilityOf(trigger, "test");
  if (!availability) return null;
  const { blockedReason } = availability;
  return (
    <BlockableButton
      variant="ghost"
      size="iconMd"
      aria-label={t("triggers.actions.testAria", { name: trigger.name })}
      blockedReason={
        blockedReason ? t(blockedReasonKey(blockedReason)) : undefined
      }
      tooltip={t("triggers.actions.test")}
      disabled={busy}
      onClick={() => onTest(trigger)}
      data-testid={`trigger-test-${trigger.id}`}
    >
      <ForwardedIconComponent
        name="Send"
        aria-hidden="true"
        className="h-4 w-4"
      />
    </BlockableButton>
  );
}

export default TriggerTestButton;
