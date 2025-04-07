import ForwardedIconComponent from "@/components/common/genericIconComponent";
import SanitizedHTMLWrapper from "@/components/common/sanitizedHTMLWrapper";
import { regexHighlight } from "@/constants/constants";
import PromptModal from "@/modals/promptModal";
import { cn } from "../../../../../utils/utils";
import { Button } from "../../../../ui/button";
import { getPlaceholder } from "../../helpers/get-placeholder-disabled";
import { InputProps, PromptAreaComponentType } from "../../types";

const promptContentClasses = {
  base: "overflow-hidden text-clip whitespace-nowrap bg-background h-fit max-h-28",
  editNode: "input-edit-node input-dialog py-2",
  normal: "primary-input text-primary",
  disabled: "disabled-state",
};

export default function PromptAreaComponent({
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
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(regexHighlight, (match, p1, p2) => {
      // Decide which group was matched. If p1 is not undefined, do nothing
      // we don't want to change the text. If p2 is not undefined, then we
      // have a variable, so we should highlight it.
      // ! This will not work with multiline or indented json yet
      if (p1 !== undefined) {
        return match;
      } else if (p2 !== undefined) {
        return `<span class="chat-message-highlight">{${p2}}</span>`;
      }

      return match;
    })
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
          {getPlaceholder(disabled, "Type your prompt here...")}
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
      <PromptModal
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
          data-testid="button_open_prompt_modal"
        >
          <div className="relative w-full">
            {renderPromptText()}
            {renderExternalLinkIcon()}
          </div>
        </Button>
      </PromptModal>
    </div>
  );
}
