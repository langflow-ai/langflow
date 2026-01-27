import type React from "react";
import { useEffect, useMemo, useRef, useState } from "react";
import { usePostValidatePrompt } from "@/controllers/API/queries/nodes/use-post-validate-prompt";
import { useGetGlobalVariables } from "@/controllers/API/queries/variables";
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
  MAX_WORDS_HIGHLIGHT,
  MUSTACHE_PROMPT_DIALOG_SUBTITLE,
} from "../../constants/constants";
import useAlertStore from "../../stores/alertStore";
import { PromptModalType } from "../../types/components";
import { handleKeyDown } from "../../utils/reactflowUtils";
import { classNames } from "../../utils/utils";
import BaseModal from "../baseModal";
import varHighlightHTML from "../promptModal/utils/var-highlight-html";

// Simple regex to extract mustache variables - only matches valid {{variable_name}} patterns
const SIMPLE_VARIABLE_PATTERN = /\{\{([a-zA-Z_][a-zA-Z0-9_]*)\}\}/g;
// Pattern for global variable references - matches {{@variable_name}} patterns
const GLOBAL_VARIABLE_PATTERN = /\{\{@([a-zA-Z_][a-zA-Z0-9_]*)\}\}/g;

// Type for non-standard caretPositionFromPoint API (not supported in Safari)
interface CaretPosition {
  offset: number;
}
interface DocumentWithCaretPosition extends Document {
  caretPositionFromPoint(x: number, y: number): CaretPosition | null;
}

export default function MustachePromptModal({
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
  const [globalVarsHighlight, setGlobalVarsHighlight] = useState<Set<string>>(
    new Set(),
  );
  const setSuccessData = useAlertStore((state) => state.setSuccessData);
  const setErrorData = useAlertStore((state) => state.setErrorData);
  const setNoticeData = useAlertStore((state) => state.setNoticeData);
  const divRef = useRef(null);
  const _divRefPrompt = useRef(null);
  const { mutate: postValidatePrompt } = usePostValidatePrompt();
  const [clickPosition, setClickPosition] = useState({ x: 0, y: 0 });
  const [scrollPosition, setScrollPosition] = useState(0);
  const previewRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Fetch global variables
  const { data: globalVariables } = useGetGlobalVariables();

  // Filter to only show Generic variables (not credentials) for prompt insertion
  const genericGlobalVariables = useMemo(() => {
    return (
      globalVariables?.filter((variable) => variable.type === "Generic") ?? []
    );
  }, [globalVariables]);

  function checkVariables(valueToCheck: string): void {
    // Extract only valid mustache variables {{variable_name}} (excluding global vars with @)
    const matches: string[] = [];
    const regex = new RegExp(SIMPLE_VARIABLE_PATTERN.source, "g");
    let match: RegExpExecArray | null = regex.exec(valueToCheck);

    while (match !== null) {
      const varName = match[1];
      // Exclude global variable references (those starting with @)
      if (!matches.includes(varName) && !varName.startsWith("@")) {
        matches.push(varName);
      }
      match = regex.exec(valueToCheck);
    }

    setWordsHighlight(new Set(matches.map((v) => `{{${v}}}`)));

    // Extract global variable references {{@variable_name}}
    const globalMatches: string[] = [];
    const globalRegex = new RegExp(GLOBAL_VARIABLE_PATTERN.source, "g");
    let globalMatch: RegExpExecArray | null = globalRegex.exec(valueToCheck);

    while (globalMatch !== null) {
      const varName = globalMatch[1];
      if (!globalMatches.includes(varName)) {
        globalMatches.push(varName);
      }
      globalMatch = globalRegex.exec(valueToCheck);
    }

    setGlobalVarsHighlight(new Set(globalMatches.map((v) => `{{@${v}}}`)));
  }

  // Insert global variable at cursor position
  const insertGlobalVariable = (variableName: string) => {
    if (!textareaRef.current || readonly) return;

    const textarea = textareaRef.current;
    const start = textarea.selectionStart;
    const end = textarea.selectionEnd;
    const text = inputValue || "";
    const insertion = `{{@${variableName}}}`;

    const newValue = text.substring(0, start) + insertion + text.substring(end);
    setInputValue(newValue);
    checkVariables(newValue);

    // Set cursor position after the inserted text
    setTimeout(() => {
      textarea.focus();
      const newPosition = start + insertion.length;
      textarea.setSelectionRange(newPosition, newPosition);
    }, 0);
  };

  useEffect(() => {
    if (inputValue && inputValue !== "") {
      checkVariables(inputValue);
    }
  }, [inputValue]);

  const coloredContent = (typeof inputValue === "string" ? inputValue : "")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    // First highlight global variables with a different color (green/teal)
    .replace(/\{\{@([a-zA-Z_][a-zA-Z0-9_]*)\}\}/g, (match) => {
      return `<span class="font-semibold text-teal-600 dark:text-teal-400">${match}</span>`;
    })
    // Then highlight regular prompt variables
    .replace(/\{\{([a-zA-Z_][a-zA-Z0-9_]*)\}\}/g, (match) => {
      return varHighlightHTML({ name: match, addCurlyBraces: false });
    })
    .replace(/\n/g, "<br />");

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
      {
        name: field_name,
        template: inputValue,
        frontend_node: nodeClass!,
        mustache: true,
      },
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
            const inputVariables = apiReturn.input_variables ?? [];
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
        const docWithCaret = document as DocumentWithCaretPosition;
        const range = docWithCaret.caretPositionFromPoint(x, y)?.offset ?? 0;
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
      <BaseModal.Header description={MUSTACHE_PROMPT_DIALOG_SUBTITLE}>
        <div className="flex w-full items-start gap-3">
          <div className="flex">
            <IconComponent
              name="TerminalSquare"
              className="h-6 w-6 pr-1 text-primary"
              aria-hidden="true"
            />
            <span className="pl-2" data-testid="modal-title">
              Edit Prompt
            </span>
          </div>
        </div>
      </BaseModal.Header>
      <BaseModal.Content overflowHidden>
        <div className="flex h-full w-full gap-4">
          {/* Main editor area */}
          <div
            className={classNames("flex flex-1 rounded-lg border", {
              "w-full": genericGlobalVariables.length === 0,
              "w-3/4": genericGlobalVariables.length > 0,
            })}
          >
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
                className={getClassByNumberLength() + " bg-muted"}
                onClick={handlePreviewClick}
                content={coloredContent}
                suppressWarning={true}
              />
            )}
          </div>

          {/* Global Variables Panel */}
          {genericGlobalVariables.length > 0 && (
            <div className="flex w-1/4 min-w-[200px] flex-col rounded-lg border bg-muted/30">
              <div className="flex items-center gap-2 border-b px-3 py-2">
                <IconComponent
                  name="Globe"
                  className="h-4 w-4 text-teal-600 dark:text-teal-400"
                />
                <span className="text-sm font-semibold">Global Variables</span>
              </div>
              <div className="flex-1 overflow-y-auto p-2 custom-scroll">
                <div className="space-y-1">
                  {genericGlobalVariables.map((variable) => (
                    <button
                      key={variable.id}
                      type="button"
                      onClick={() => {
                        setIsEdit(true);
                        setTimeout(() => insertGlobalVariable(variable.name), 0);
                      }}
                      disabled={readonly}
                      className="flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left text-sm transition-colors hover:bg-muted disabled:cursor-not-allowed disabled:opacity-50"
                    >
                      <IconComponent
                        name="Plus"
                        className="h-3 w-3 text-muted-foreground"
                      />
                      <span className="truncate font-mono text-xs">
                        {variable.name}
                      </span>
                    </button>
                  ))}
                </div>
              </div>
              <div className="border-t px-3 py-2">
                <p className="text-xs text-muted-foreground">
                  Click to insert <code className="text-teal-600 dark:text-teal-400">{`{{@var}}`}</code> at cursor
                </p>
              </div>
            </div>
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

                  {/* Show global variables used in the template */}
                  {globalVarsHighlight.size > 0 && (
                    <>
                      <IconComponent
                        name="Globe"
                        className="ml-2 flex h-4 w-4 text-teal-600 dark:text-teal-400"
                      />
                      <span className="text-md font-semibold text-teal-600 dark:text-teal-400">
                        Global:
                      </span>
                      {Array.from(globalVarsHighlight).map((word, index) => (
                        <ShadTooltip
                          key={`global-${index}`}
                          content={word.replace(/[{}@]/g, "")}
                          asChild={false}
                        >
                          <Badge
                            key={`global-${index}`}
                            variant="secondary"
                            size="md"
                            className="max-w-[40vw] cursor-default truncate border-teal-600/30 bg-teal-50 p-1 text-sm text-teal-700 dark:border-teal-400/30 dark:bg-teal-950 dark:text-teal-300"
                          >
                            <div className="relative bottom-[1px]">
                              <span id={"global-badge" + index.toString()}>
                                {word.replace(/[{}@]/g, "").length > 59
                                  ? word.replace(/[{}@]/g, "").slice(0, 56) +
                                    "..."
                                  : word.replace(/[{}@]/g, "")}
                              </span>
                            </div>
                          </Badge>
                        </ShadTooltip>
                      ))}
                    </>
                  )}
                </div>
              </div>
              <span className="mt-2 text-xs text-muted-foreground">
                Use <code>{`{{variable}}`}</code> for input fields, or{" "}
                <code className="text-teal-600 dark:text-teal-400">{`{{@global_var}}`}</code>{" "}
                to reference global variables
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
