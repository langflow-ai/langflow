import { useTranslation } from "react-i18next";
import langflowAssistantIcon from "@/assets/langflow_assistant.svg";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import {
  Empty,
  EmptyContent,
  EmptyMedia,
  EmptyTitle,
} from "@/components/ui/empty-state";
import { ASSISTANT_SUGGESTIONS } from "../assistant-panel.constants";

interface AssistantEmptyStateProps {
  onSuggestionClick: (suggestion: string) => void;
}

export function AssistantEmptyState({
  onSuggestionClick,
}: AssistantEmptyStateProps) {
  const { t } = useTranslation();
  return (
    <Empty className="flex-1 px-8">
      <EmptyMedia className="mb-6 h-16 w-16 overflow-hidden rounded-2xl">
        <img
          src={langflowAssistantIcon}
          alt={t("assistant.title")}
          className="h-full w-full object-cover"
        />
      </EmptyMedia>
      <EmptyTitle className="mb-6 text-center text-base leading-6 tracking-normal text-foreground">
        {t("assistant.welcomeText")}
      </EmptyTitle>
      <EmptyContent className="flex-col gap-2">
        {ASSISTANT_SUGGESTIONS.map((suggestion) => (
          <Button
            key={suggestion.id}
            variant="outline"
            className="h-[46px] w-[265px] justify-start gap-2 rounded-xl border border-border bg-muted/50 px-3 text-[13px] font-medium leading-4 text-foreground hover:bg-muted"
            onClick={() => onSuggestionClick(suggestion.text)}
          >
            <ForwardedIconComponent
              name={suggestion.icon}
              className="h-5 w-5 text-foreground"
            />
            {t(`assistant.suggestion.${suggestion.id}`)}
          </Button>
        ))}
      </EmptyContent>
    </Empty>
  );
}
