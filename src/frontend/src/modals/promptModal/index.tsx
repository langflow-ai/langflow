import { usePostValidatePrompt } from "@/controllers/API/queries/nodes/use-post-validate-prompt";
import React, { useEffect, useRef, useState } from "react";
import IconComponent from "../../components/common/genericIconComponent";
import SanitizedHTMLWrapper from "../../components/common/sanitizedHTMLWrapper";
import ShadTooltip from "../../components/common/shadTooltipComponent";
import { Badge } from "../../components/ui/badge";
import { Button } from "../../components/ui/button";
import { Textarea } from "../../components/ui/textarea";
import {
  BUG_ALERT,
  PROMPT_ERROR_ALERT,
  PROMPT_SUCCESS_ALERT,
  TEMP_NOTICE_ALERT,
} from "../../constants/alerts_constants";
import {
  EDIT_TEXT_PLACEHOLDER,
  INVALID_CHARACTERS,
  MAX_WORDS_HIGHLIGHT,
  PROMPT_DIALOG_SUBTITLE,
  regexHighlight,
} from "../../constants/constants";
import useAlertStore from "../../stores/alertStore";
import { PromptModalType } from "../../types/components";
import { handleKeyDown } from "../../utils/reactflowUtils";
import { classNames } from "../../utils/utils";
import BaseModal from "../baseModal";
import varHighlightHTML from "./utils/var-highlight-html";

export default function PromptModal({
  field_name = "",
  value,
  setValue,
  nodeClass,
  setNodeClass,
  children,
  disabled,
  id = "",
  readonly = false,
}: PromptModalType): JSX.Element {
  const [modalOpen, setModalOpen] = useState(false);
  const [inputValue, setInputValue] = useState(value);
  const [isEdit, setIsEdit] = useState(true);
  const [wordsHighlight, setWordsHighlight] = useState<Set<string>>(new Set());
  const setSuccessData = useAlertStore((state) => state.setSuccessData);
  const setErrorData = useAlertStore((state) => state.setErrorData);
  const setNoticeData = useAlertStore((state) => state.setNoticeData);
  const divRef = useRef(null);
  const divRefPrompt = useRef(null);
  const { mutate: postValidatePrompt } = usePostValidatePrompt();
  const [clickPosition, setClickPosition] = useState({ x: 0, y: 0 });
  const [scrollPosition, setScrollPosition] = useState(0);
  const previewRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  function checkVariables(valueToCheck: string): void {
    const regex = /\{([^{}]+)\}/g;
    const matches: string[] = [];
    let match;
    while ((match = regex.exec(valueToCheck))) {
      matches.push(`{${match[1]}}`);
    }

    let invalid_chars: string[] = [];
    let fixed_variables: string[] = [];
    let input_variables = matches;
    for (let variable of input_variables) {
      let new_var = variable;
      for (let char of INVALID_CHARACTERS) {
        if (variable.includes(char)) {
          invalid_chars.push(new_var);
        }
      }
      fixed_variables.push(new_var);
      if (new_var !== variable) {
        const index = input_variables.indexOf(variable);
        if (index !== -1) {
          input_variables.splice(index, 1, new_var);
        }
      }
    }

    const filteredWordsHighlight = new Set(
      matches.filter((word) => !invalid_chars.includes(word)),
    );

    setWordsHighlight(filteredWordsHighlight);
  }

  const coloredContent = (typeof inputValue === "string" ? inputValue : "")
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
        return varHighlightHTML({ name: p2 });
      }

      return match;
    })
    .replace(/\n/g, "<br />");

  useEffect(() => {
    if (inputValue && inputValue != "") {
      checkVariables(inputValue);
    }
  }, [inputValue]);

  useEffect(() => {
    if (typeof value === "string") setInputValue(value);
  }, [value, modalOpen]);

  function getClassByNumberLength(): string {
    let sumOfCaracteres: number = 0;
    wordsHighlight.forEach((element) => {
      sumOfCaracteres = sumOfCaracteres + element.replace(/[{}]/g, "").length;
    });
    return sumOfCaracteres > MAX_WORDS_HIGHLIGHT
      ? "code-highlight"
      : "code-nohighlight";
  }

  // Function need some review, working for now
  function validatePrompt(closeModal: boolean): void {
    //nodeClass is always null on tweaks
    postValidatePrompt(
      { name: field_name, template: inputValue, frontend_node: nodeClass! },
      {
        onSuccess: (apiReturn) => {
          if (field_name === "") {
            field_name = Array.isArray(
              apiReturn?.frontend_node?.custom_fields?.[""],
            )
              ? (apiReturn?.frontend_node?.custom_fields?.[""][0] ?? "")
              : (apiReturn?.frontend_node?.custom_fields?.[""] ?? "");
          }
          if (apiReturn) {
            let inputVariables = apiReturn.input_variables ?? [];
            if (
              JSON.stringify(apiReturn?.frontend_node) !== JSON.stringify({})
            ) {
              setValue(inputValue);
              apiReturn.frontend_node.template.template.value = inputValue;
              if (setNodeClass) setNodeClass(apiReturn?.frontend_node);
              setModalOpen(closeModal);
              setIsEdit(false);
            }
            if (!inputVariables || inputVariables.length === 0) {
              setNoticeData({
                title: TEMP_NOTICE_ALERT,
              });
            } else {
              setSuccessData({
                title: PROMPT_SUCCESS_ALERT,
              });
            }
          } else {
            setIsEdit(true);
            setErrorData({
              title: BUG_ALERT,
            });
          }
        },
        onError: (error) => {
          setIsEdit(true);
          return setErrorData({
            title: PROMPT_ERROR_ALERT,
            list: [error.response.data.detail ?? ""],
          });
        },
      },
    );
  }

  const handlePreviewClick = (e: React.MouseEvent<HTMLDivElement>) => {
    if (!isEdit && !readonly) {
      const clickX = e.clientX;
      const clickY = e.clientY;
      setClickPosition({ x: clickX, y: clickY });
      setScrollPosition(e.currentTarget.scrollTop);
      setIsEdit(true);
    }
  };

  useEffect(() => {
    if (isEdit && textareaRef.current) {
      textareaRef.current.focus();
      textareaRef.current.scrollTop = scrollPosition;

      const textArea = textareaRef.current;
      const { x, y } = clickPosition;

      // Use caretPositionFromPoint to get the closest text position. Does not work on Safari.
      if ("caretPositionFromPoint" in document) {
        let range = (document as any).caretPositionFromPoint(x, y)?.offset ?? 0;
        if (range) {
          const position = range;
          textArea.setSelectionRange(position, position);
        }
      }
    } else if (!isEdit && previewRef.current) {
      previewRef.current.scrollTop = scrollPosition;
    }
  }, [isEdit, clickPosition, scrollPosition]);

  return (
    <BaseModal
      onChangeOpenModal={(open) => {}}
      open={modalOpen}
      setOpen={setModalOpen}
      size="x-large"
    >
      <BaseModal.Trigger disable={disabled} asChild>
        {children}
      </BaseModal.Trigger>
      <BaseModal.Header description={PROMPT_DIALOG_SUBTITLE}>
        <div className="flex w-full items-start gap-3">
          <div className="flex">
            <span className="pr-2" data-testid="modal-title">
              Edit Prompt
            </span>
            <IconComponent
              name="TerminalSquare"
              className="h-6 w-6 pl-1 text-primary"
              aria-hidden="true"
            />
          </div>
        </div>
      </BaseModal.Header>
      <BaseModal.Content overflowHidden>
        <div className={classNames("flex h-full w-full rounded-lg border")}>
          {isEdit && !readonly ? (
            <Textarea
              id={"modal-" + id}
              data-testid={"modal-" + id}
              ref={textareaRef}
              className="form-input h-full w-full resize-none rounded-lg border-0 custom-scroll focus-visible:ring-1"
              value={inputValue}
              onBlur={() => {
                setScrollPosition(textareaRef.current?.scrollTop || 0);
                setIsEdit(false);
              }}
              autoFocus
              onChange={(event) => {
                setInputValue(event.target.value);
                checkVariables(event.target.value);
              }}
              placeholder={EDIT_TEXT_PLACEHOLDER}
              onKeyDown={(e) => {
                handleKeyDown(e, inputValue, "");
              }}
            />
          ) : (
            <SanitizedHTMLWrapper
              ref={previewRef}
              className={getClassByNumberLength() + " m-0"}
              onClick={handlePreviewClick}
              content={coloredContent}
              suppressWarning={true}
            />
          )}
        </div>
      </BaseModal.Content>
      <BaseModal.Footer>
        <div className="flex w-full shrink-0 items-end justify-between">
          <div className="mb-auto flex-1">
            <div className="mr-2">
              <div
                ref={divRef}
                className="max-h-20 overflow-y-auto custom-scroll"
              >
                <div className="flex flex-wrap items-center gap-2">
                  <IconComponent
                    name="Braces"
                    className="flex h-4 w-4 text-primary"
                  />
                  <span className="text-md font-semibold text-primary">
                    Prompt Variables:
                  </span>

                  {Array.from(wordsHighlight).map((word, index) => (
                    <ShadTooltip
                      key={index}
                      content={word.replace(/[{}]/g, "")}
                      asChild={false}
                    >
                      <Badge
                        key={index}
                        variant="gray"
                        size="md"
                        className="max-w-[40vw] cursor-default truncate p-1 text-sm"
                      >
                        <div className="relative bottom-[1px]">
                          <span id={"badge" + index.toString()}>
                            {word.replace(/[{}]/g, "").length > 59
                              ? word.replace(/[{}]/g, "").slice(0, 56) + "..."
                              : word.replace(/[{}]/g, "")}
                          </span>
                        </div>
                      </Badge>
                    </ShadTooltip>
                  ))}
                </div>
              </div>
              <span className="mt-2 text-xs text-muted-foreground">
                Prompt variables can be created with any chosen name inside
                curly brackets, e.g. {"{variable_name}"}
              </span>
            </div>
          </div>
          <Button
            data-testid="genericModalBtnSave"
            id="genericModalBtnSave"
            disabled={readonly}
            onClick={() => {
              validatePrompt(false);
            }}
            type="submit"
          >
            Check & Save
          </Button>
        </div>
      </BaseModal.Footer>
    </BaseModal>
  );
}
