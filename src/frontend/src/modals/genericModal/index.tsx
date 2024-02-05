import { useContext, useEffect, useRef, useState } from "react";
import SanitizedHTMLWrapper from "../../components/SanitizedHTMLWrapper";
import ShadTooltip from "../../components/ShadTooltipComponent";
import IconComponent from "../../components/genericIconComponent";
import { Badge } from "../../components/ui/badge";
import { Button } from "../../components/ui/button";
import { Textarea } from "../../components/ui/textarea";
import {
  INVALID_CHARACTERS,
  MAX_WORDS_HIGHLIGHT,
  PROMPT_DIALOG_SUBTITLE,
  TEXT_DIALOG_SUBTITLE,
  regexHighlight,
} from "../../constants/constants";
import { TypeModal } from "../../constants/enums";
import { alertContext } from "../../contexts/alertContext";
import { postValidatePrompt } from "../../controllers/API";
import { genericModalPropsType } from "../../types/components";
import { handleKeyDown } from "../../utils/reactflowUtils";
import { classNames, varHighlightHTML } from "../../utils/utils";
import BaseModal from "../baseModal";

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
  id = "",
  readonly = false,
}: genericModalPropsType): JSX.Element {
  const [myButtonText] = useState(buttonText);
  const [myModalTitle] = useState(modalTitle);
  const [modalOpen, setModalOpen] = useState(false);
  const [myModalType] = useState(type);
  const [inputValue, setInputValue] = useState(value);
  const [isEdit, setIsEdit] = useState(true);
  const [wordsHighlight, setWordsHighlight] = useState<string[]>([]);
  const { setErrorData, setSuccessData, setNoticeData, setModalContextOpen } =
    useContext(alertContext);
  const ref = useRef();
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

    const filteredWordsHighlight = matches.filter(
      (word) => !invalid_chars.includes(word)
    );

    setWordsHighlight(filteredWordsHighlight);
  }

  useEffect(() => {
    if (type === TypeModal.PROMPT && inputValue && inputValue != "") {
      checkVariables(inputValue);
    }
  }, [inputValue, type]);

  useEffect(() => {
    setInputValue(value);
  }, [value, modalOpen]);

  const coloredContent = (inputValue || "")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(regexHighlight, varHighlightHTML({ name: "$1" }))
    .replace(/\n/g, "<br />");

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
            apiReturn.data?.frontend_node?.custom_fields?.[""]
          )
            ? apiReturn.data?.frontend_node?.custom_fields?.[""][0] ?? ""
            : apiReturn.data?.frontend_node?.custom_fields?.[""] ?? "";
        }
        if (apiReturn.data) {
          let inputVariables = apiReturn.data.input_variables ?? [];
          if (
            JSON.stringify(apiReturn.data?.frontend_node) !== JSON.stringify({})
          ) {
            setNodeClass!(apiReturn.data?.frontend_node, inputValue);
            setModalOpen(closeModal);
            setIsEdit(false);
          }
          if (!inputVariables || inputVariables.length === 0) {
            setNoticeData({
              title: "Your template does not have any variables.",
            });
          } else {
            setSuccessData({
              title: "Prompt is ready",
            });
          }
        } else {
          setIsEdit(true);
          setErrorData({
            title: "Something went wrong, please try again",
          });
        }
      })
      .catch((error) => {
        console.log(error);
        setIsEdit(true);
        return setErrorData({
          title: "There is something wrong with this prompt, please review it",
          list: [error.toString()],
        });
      });
  }

  useEffect(() => {
    setModalContextOpen(modalOpen);
  }, [modalOpen]);

  return (
    <BaseModal
      onChangeOpenModal={(open) => {}}
      open={modalOpen}
      setOpen={setModalOpen}
    >
      <BaseModal.Trigger>{children}</BaseModal.Trigger>
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
          name="FileText"
          className="h-6 w-6 pl-1 text-primary "
          aria-hidden="true"
        />
      </BaseModal.Header>
      <BaseModal.Content>
        <div className="flex h-full flex-col">
          <div
            className={classNames(
              !isEdit ? "rounded-lg border" : "",
              "flex h-full w-full"
            )}
          >
            {type === TypeModal.PROMPT && isEdit && !readonly ? (
              <Textarea
                id={"modal-" + id}
                data-testid={"modal-" + id}
                ref={divRefPrompt}
                className="form-input h-full w-full rounded-lg custom-scroll focus-visible:ring-1"
                value={inputValue}
                onBlur={() => {
                  setIsEdit(false);
                }}
                autoFocus
                onChange={(event) => {
                  setInputValue(event.target.value);
                  checkVariables(event.target.value);
                }}
                placeholder="Type message here."
                onKeyDown={(e) => {
                  handleKeyDown(e, inputValue, "");
                }}
              />
            ) : type === TypeModal.PROMPT && (!isEdit || readonly) ? (
              <SanitizedHTMLWrapper
                className={getClassByNumberLength()}
                content={coloredContent}
                onClick={() => {
                  setIsEdit(true);
                }}
                suppressWarning={true}
              />
            ) : type !== TypeModal.PROMPT ? (
              <Textarea
                //@ts-ignore
                ref={ref}
                className="form-input h-full w-full rounded-lg focus-visible:ring-1"
                value={inputValue}
                onChange={(event) => {
                  setInputValue(event.target.value);
                }}
                placeholder="Type message here."
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

          <div className="mt-6 flex h-fit w-full items-end justify-between">
            <div className="mb-auto flex-1">
              {type === TypeModal.PROMPT && (
                <div className=" mr-2">
                  <div
                    ref={divRef}
                    className="max-h-20 overflow-y-auto custom-scroll"
                  >
                    <div className="flex flex-wrap items-center">
                      <IconComponent
                        name="Variable"
                        className=" -ml-px mr-1 flex h-4 w-4 text-primary"
                      />
                      <span className="text-md font-semibold text-primary">
                        Prompt Variables:
                      </span>

                      {wordsHighlight.map((word, index) => (
                        <ShadTooltip
                          key={index}
                          content={word.replace(/[{}]/g, "")}
                          asChild={false}
                        >
                          <Badge
                            key={index}
                            variant="gray"
                            size="md"
                            className="m-1 max-w-[40vw] cursor-default truncate p-2.5 text-sm"
                          >
                            <div className="relative bottom-[1px]">
                              <span id={"badge" + index.toString()}>
                                {word.replace(/[{}]/g, "").length > 59
                                  ? word.replace(/[{}]/g, "").slice(0, 56) +
                                    "..."
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
        </div>
      </BaseModal.Content>
    </BaseModal>
  );
}
