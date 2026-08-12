import { useTranslation } from "react-i18next";
import langflowAssistantIcon from "@/assets/langflow_assistant.svg";

export function AssistantDisabledState() {
  const { t } = useTranslation();

  return (
    <div
      className="flex flex-1 flex-col items-center justify-center px-8 pb-6"
      data-testid="assistant-disabled-state"
    >
      <div className="mb-6 flex h-16 w-16 items-center justify-center overflow-hidden rounded-2xl">
        <img
          src={langflowAssistantIcon}
          alt={t("assistant.title")}
          className="h-full w-full object-cover"
        />
      </div>
      <h3 className="mb-3 text-center text-base font-semibold leading-6 tracking-normal text-foreground">
        {t("assistant.disabledTitle")}
      </h3>
      <p className="mb-3 max-w-[320px] text-center text-sm text-muted-foreground">
        {t("assistant.disabledDescription")}
      </p>
      <code className="rounded-md bg-muted px-2 py-1 text-xs text-foreground">
        LANGFLOW_AGENTIC_EXPERIENCE=true
      </code>
    </div>
  );
}
