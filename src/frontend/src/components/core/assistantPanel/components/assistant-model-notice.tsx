import { useTranslation } from "react-i18next";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import ShadTooltip from "@/components/common/shadTooltipComponent";
import type { AssistantModelNotice as AssistantModelNoticeType } from "@/controllers/API/queries/agentic";

interface AssistantModelNoticeProps {
  notices: AssistantModelNoticeType[];
}

/**
 * An (i) shown next to a completed assistant message when the turn recovered
 * from a silent model failure (the user's model errored in the background and
 * the assistant fell back or retried). Hovering explains what happened so the
 * swap is never hidden.
 */
export function AssistantModelNotice({ notices }: AssistantModelNoticeProps) {
  const { t } = useTranslation();
  if (!notices || notices.length === 0) return null;

  const describe = (n: AssistantModelNoticeType): string => {
    if (n.type === "model_fallback" && n.used_model) {
      return t("assistant.modelNotice.fallback", {
        failed: n.failed_model ?? "?",
        used: n.used_model,
        reason: n.reason,
      });
    }
    return t("assistant.modelNotice.remediation", {
      failed: n.failed_model ?? "?",
      reason: n.reason,
    });
  };

  const content = (
    <div className="flex max-w-xs flex-col gap-1 text-left">
      {notices.map((n, i) => (
        <span key={`${n.type}-${i}`} className="text-xs leading-4">
          {describe(n)}
        </span>
      ))}
    </div>
  );

  return (
    <ShadTooltip content={content} side="bottom">
      <span
        className="inline-flex cursor-help items-center text-amber-500"
        aria-label={t("assistant.modelNotice.ariaLabel")}
        data-testid="assistant-model-notice"
      >
        <ForwardedIconComponent name="Info" className="h-3.5 w-3.5" />
      </span>
    </ShadTooltip>
  );
}
