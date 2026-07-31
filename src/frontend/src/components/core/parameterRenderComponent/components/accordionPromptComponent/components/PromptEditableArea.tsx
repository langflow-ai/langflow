import type { FormEvent, KeyboardEvent, RefObject } from "react";
import { useTranslation } from "react-i18next";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import MustachePromptModal from "@/modals/mustachePromptModal";
import PromptModal from "@/modals/promptModal";
import type { APIClassType } from "@/types/api";
import { cn } from "@/utils/utils";
import { getPlaceholder } from "../../../helpers/get-placeholder-disabled";

export function PromptEditableArea({
  contentEditableRef,
  disabled,
  readonly,
  id,
  internalValue,
  isScrollable,
  isDoubleBrackets,
  field_name,
  value,
  nodeClass,
  handleNodeClass,
  onInput,
  onKeyDown,
  onPromptModalSetValue,
}: {
  contentEditableRef: RefObject<HTMLDivElement | null>;
  disabled?: boolean;
  readonly?: boolean;
  id: string;
  internalValue: string;
  isScrollable: boolean;
  isDoubleBrackets: boolean;
  field_name?: string;
  value: string;
  nodeClass?: APIClassType;
  // biome-ignore lint/suspicious/noExplicitAny: legacy
  handleNodeClass?: (value: any, code?: string, type?: string) => void;
  onInput: (e: FormEvent<HTMLDivElement>) => void;
  onKeyDown: (e: KeyboardEvent<HTMLDivElement>) => void;
  onPromptModalSetValue: (newValue: string) => void;
}) {
  const { t } = useTranslation();
  const ModalComponent = isDoubleBrackets ? MustachePromptModal : PromptModal;

  return (
    <div className="relative">
      <div
        ref={contentEditableRef}
        contentEditable={!disabled && !readonly}
        onInput={onInput}
        onKeyDown={onKeyDown}
        suppressContentEditableWarning
        id={id}
        data-testid={id}
        className={cn(
          "relative min-h-10 overflow-y-auto rounded-md border bg-background px-3 py-2 pr-8 text-sm outline-none break-words whitespace-pre-wrap",
          "focus:border-primary hover:border-muted-foreground",
          "before:content-[''] before:pointer-events-none before:absolute before:left-3 before:top-2 before:text-muted-foreground",
          "empty:before:content-[attr(data-placeholder)]",
          disabled && "cursor-not-allowed opacity-50",
          readonly && "cursor-default",
          !internalValue && "text-muted-foreground",
        )}
        data-placeholder={getPlaceholder(disabled, "Type your prompt here...")}
      />
      {!disabled && (
        <div
          className={cn(
            "absolute top-2 z-10 flex items-center gap-1",
            isScrollable ? "right-3" : "right-1",
          )}
        >
          <ModalComponent
            id={id}
            field_name={field_name}
            readonly={readonly}
            value={value}
            setValue={onPromptModalSetValue}
            nodeClass={nodeClass}
            setNodeClass={handleNodeClass}
          >
            <Button
              type="button"
              variant="ghost"
              size="sm"
              className="h-6 w-6 p-0 text-muted-foreground"
              title={t("accordion.fullscreen")}
              data-testid={
                isDoubleBrackets
                  ? "button_open_mustache_prompt_modal"
                  : "button_open_prompt_modal"
              }
            >
              <ForwardedIconComponent name="Maximize" className="h-3.5 w-3.5" />
            </Button>
          </ModalComponent>
        </div>
      )}
    </div>
  );
}
