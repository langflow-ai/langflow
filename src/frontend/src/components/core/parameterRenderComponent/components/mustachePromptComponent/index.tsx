import ForwardedIconComponent from "@/components/common/genericIconComponent";
import SanitizedHTMLWrapper from "@/components/common/sanitizedHTMLWrapper";
import MustachePromptModal from "@/modals/mustachePromptModal";
import { cn } from "../../../../../utils/utils";
import { Button } from "../../../../ui/button";
import { getPlaceholder } from "../../helpers/get-placeholder-disabled";
import type { InputProps, PromptAreaComponentType } from "../../types";

const promptContentClasses = {
  base: "overflow-hidden text-clip whitespace-nowrap bg-background h-fit max-h-28",
  editNode: "input-edit-node input-dialog py-2",
  normal: "primary-input text-primary",
  disabled: "disabled-state",
};

export default function MustachePromptAreaComponent({
  field_name,
  nodeClass,
  handleOnNewValue,
  handleNodeClass,
  value,
  disabled,
  editNode = false,
  id = "",
  readonly = false,
}: InputProps<string, PromptAreaComponentType>): JSX.Element {
  const coloredContent = (typeof value === "string" ? value : "")
    // escape HTML first
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    // highlight mustache variables {{variable}}
    .replace(/\{\{(.+?)\}\}/g, (match, varName) => {
      return `<span class="chat-message-highlight">{{${varName}}}</span>`;
    })
    // preserve new-lines
    .replace(/\n/g, "<br />");

  const renderPromptText = () => (
    <span
      id={id}
      data-testid={id}
      className={cn(
        promptContentClasses.base,
        editNode ? promptContentClasses.editNode : promptContentClasses.normal,
        disabled && !editNode && promptContentClasses.disabled,
      )}
    >
      {value !== "" ? (
        <SanitizedHTMLWrapper
          className="m-0 whitespace-pre-wrap p-0 text-xs"
          content={coloredContent}
          suppressWarning={true}
        />
      ) : (
        <span className="text-sm text-muted-foreground">
          {getPlaceholder(disabled, "Type your mustache prompt here...")}
        </span>
      )}
    </span>
  );

  const renderExternalLinkIcon = () =>
    !value || value == "" ? (
      <ForwardedIconComponent
        name={disabled ? "lock" : "Scan"}
        className={cn(
          "icons-parameters-comp pointer-events-none absolute right-3 top-1/2 h-4 w-4 shrink-0 -translate-y-1/2",
          disabled ? "text-placeholder-foreground" : "text-foreground",
        )}
      />
    ) : (
      <></>
    );

  return (
    <div className={cn("w-full", disabled && "pointer-events-none")}>
      <MustachePromptModal
        id={id}
        field_name={field_name}
        readonly={readonly}
        value={value}
        setValue={(newValue) => handleOnNewValue({ value: newValue })}
        nodeClass={nodeClass}
        setNodeClass={handleNodeClass}
      >
        <Button
          unstyled
          className="w-full"
          data-testid="button_open_mustache_prompt_modal"
        >
          <div className="relative w-full">
            {renderPromptText()}
            {renderExternalLinkIcon()}
          </div>
        </Button>
      </MustachePromptModal>
    </div>
  );
}
