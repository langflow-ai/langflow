import { useEffect, useRef, useState } from "react";
import IconComponent from "../../components/genericIconComponent";
import SanitizedHTMLWrapper from "../../components/sanitizedHTMLWrapper";
import ShadTooltip from "../../components/shadTooltipComponent";
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
  TEXT_DIALOG_SUBTITLE,
  regexHighlight,
} from "../../constants/constants";
import { TypeModal } from "../../constants/enums";
import { postValidatePrompt } from "../../controllers/API";
import useAlertStore from "../../stores/alertStore";
import { genericModalPropsType } from "../../types/components";
import { handleKeyDown } from "../../utils/reactflowUtils";
import { classNames } from "../../utils/utils";
import BaseModal from "../baseModal";
import varHighlightHTML from "./utils/var-highlight-html";

export default function GenericModal({
  field_name = "",
  value,
  setValue,
  buttonText,
  modalTitle,
  type,
  nodeClass,
  setNodeClass,
  children,
  disabled,
  id = "",
  readonly = false,
}: genericModalPropsType): JSX.Element {
  const [myButtonText] = useState(buttonText);
  const [myModalTitle] = useState(modalTitle);
  const [modalOpen, setModalOpen] = useState(false);
  const [myModalType] = useState(type);
  const [inputValue, setInputValue] = useState(value);
  const [isEdit, setIsEdit] = useState(true);
  const [wordsHighlight, setWordsHighlight] = useState<Set<string>>(new Set());
  const setSuccessData = useAlertStore((state) => state.setSuccessData);
  const setErrorData = useAlertStore((state) => state.setErrorData);
  const setNoticeData = useAlertStore((state) => state.setNoticeData);
  const textRef = useRef<HTMLTextAreaElement>(null);
  const divRef = useRef(null);
  const divRefPrompt = useRef(null);

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
    if (type === TypeModal.PROMPT && inputValue && inputValue != "") {
      checkVariables(inputValue);
    }
  }, [inputValue, type]);

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
    postValidatePrompt(field_name, inputValue, nodeClass!)
      .then((apiReturn) => {
        // if field_name is an empty string, then we need to set it
        // to the first key of the custom_fields object
        if (field_name === "") {
          field_name = Array.isArray(
            apiReturn.data?.frontend_node?.custom_fields?.[""],
          )
            ? apiReturn.data?.frontend_node?.custom_fields?.[""][0] ?? ""
            : apiReturn.data?.frontend_node?.custom_fields?.[""] ?? "";
        }
        if (apiReturn.data) {
          let inputVariables = apiReturn.data.input_variables ?? [];
          if (
            JSON.stringify(apiReturn.data?.frontend_node) !== JSON.stringify({})
          ) {
            if (setNodeClass)
              setNodeClass(apiReturn.data?.frontend_node, inputValue);
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
      })
      .catch((error) => {
        setIsEdit(true);
        return setErrorData({
          title: PROMPT_ERROR_ALERT,
          list: [error.response.data.detail ?? ""],
        });
      });
  }

  return (
    <BaseModal
      onChangeOpenModal={(open) => {}}
      open={modalOpen}
      setOpen={setModalOpen}
    >
      <BaseModal.Trigger disable={disabled} asChild>
        {children}
      </BaseModal.Trigger>
      <BaseModal.Header
        description={(() => {
          switch (myModalTitle) {
            case "Edit Text":
              return TEXT_DIALOG_SUBTITLE;

            case "Edit Prompt":
              return PROMPT_DIALOG_SUBTITLE;

            default:
              return null;
          }
        })()}
      >
        <span className="pr-2" data-testid="modal-title">
          {myModalTitle}
        </span>
        <IconComponent
          name={myModalTitle === "Edit Prompt" ? "TerminalSquare" : "FileText"}
          className="h-6 w-6 pl-1 text-primary"
          aria-hidden="true"
        />
      </BaseModal.Header>
      <BaseModal.Content overflowHidden>
        <div className={classNames("flex h-full w-full rounded-lg border")}>
          {type === TypeModal.PROMPT && isEdit && !readonly ? (
            <Textarea
              id={"modal-" + id}
              data-testid={"modal-" + id}
              ref={divRefPrompt}
              className="form-input h-full w-full resize-none rounded-lg custom-scroll focus-visible:ring-1"
              value={inputValue}
              onBlur={() => {
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
          ) : type === TypeModal.PROMPT && (!isEdit || readonly) ? (
            <SanitizedHTMLWrapper
              className={getClassByNumberLength() + " bg-muted"}
              content={coloredContent}
              onClick={() => {
                setIsEdit(true);
              }}
              suppressWarning={true}
            />
          ) : type !== TypeModal.PROMPT ? (
            <Textarea
              ref={textRef}
              className="form-input h-full w-full resize-none overflow-auto rounded-lg focus-visible:ring-1"
              value={inputValue}
              onChange={(event) => {
                setInputValue(event.target.value);
              }}
              placeholder={EDIT_TEXT_PLACEHOLDER}
              onKeyDown={(e) => {
                handleKeyDown(e, value, "");
              }}
              readOnly={readonly}
              id={"text-area-modal"}
              data-testid={"text-area-modal"}
            />
          ) : (
            <></>
          )}
        </div>
      </BaseModal.Content>
      <BaseModal.Footer>
        <div className="flex w-full shrink-0 items-end justify-between">
          <div className="mb-auto flex-1">
            {type === TypeModal.PROMPT && (
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
            )}
          </div>
          <Button
            data-testid="genericModalBtnSave"
            id="genericModalBtnSave"
            disabled={readonly}
            onClick={() => {
              switch (myModalType) {
                case TypeModal.TEXT:
                  setValue(inputValue);
                  setModalOpen(false);
                  break;
                case TypeModal.PROMPT:
                  validatePrompt(false);
                  break;

                default:
                  break;
              }
            }}
            type="submit"
          >
            {myButtonText}
          </Button>
        </div>
      </BaseModal.Footer>
    </BaseModal>
  );
}
