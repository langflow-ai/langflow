import { ReactNode, useContext, useEffect, useRef, useState } from "react";
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
import { APIClassType } from "../../types/api";
import {
  classNames,
  getRandomKeyByssmm,
  varHighlightHTML,
} from "../../utils/utils";
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
}: {
  field_name?: string;
  setValue: (value: string) => void;
  value: string;
  buttonText: string;
  modalTitle: string;
  type: number;
  children: ReactNode;
  nodeClass?: APIClassType;
  setNodeClass?: (Class: APIClassType) => void;
}) {
  const [myButtonText] = useState(buttonText);
  const [myModalTitle] = useState(modalTitle);
  const [myModalType] = useState(type);
  const [inputValue, setInputValue] = useState(value);
  const [isEdit, setIsEdit] = useState(true);
  const [wordsHighlight, setWordsHighlight] = useState([]);
  const { setErrorData, setSuccessData, setNoticeData } =
    useContext(alertContext);
  const ref = useRef();
  const divRef = useRef(null);
  const divRefPrompt = useRef(null);

  function checkVariables(valueToCheck) {
    const regex = /\{([^{}]+)\}/g;
    const matches = [];
    let match;
    while ((match = regex.exec(valueToCheck))) {
      matches.push(`{${match[1]}}`);
    }

    let invalid_chars = [];
    let fixed_variables = [];
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
  }, [value]);

  const coloredContent = (inputValue || "")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(regexHighlight, varHighlightHTML({ name: "$1" }))
    .replace(/\n/g, "<br />");

  const TextAreaContentView = () => {
    return (
      <SanitizedHTMLWrapper
        className={getClassByNumberLength()}
        content={coloredContent}
        onClick={() => {
          setIsEdit(true);
        }}
        suppressWarning={true}
      />
    );
  };

  function getClassByNumberLength() {
    let sumOfCaracteres: number = 0;
    wordsHighlight.forEach((element) => {
      sumOfCaracteres = sumOfCaracteres + element.replace(/[{}]/g, "").length;
    });
    return sumOfCaracteres > MAX_WORDS_HIGHLIGHT
      ? "code-highlight"
      : "code-nohighlight";
  }

  function validatePrompt(closeModal: boolean) {
    postValidatePrompt(field_name, inputValue, nodeClass)
      .then((apiReturn) => {
        if (apiReturn.data) {
          let inputVariables = apiReturn.data.input_variables ?? [];
          if (inputVariables && inputVariables.length === 0) {
            setIsEdit(true);
            setNoticeData({
              title: "Your template does not have any variables.",
            });
          } else {
            setIsEdit(false);
            setSuccessData({
              title: "Prompt is ready",
            });
            setNodeClass(apiReturn.data?.frontend_node);
            setModalOpen(closeModal);
            setValue(inputValue);
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
          list: [error?.response?.data?.detail],
        });
      });
  }

  const [modalOpen, setModalOpen] = useState(false);

  return (
    <BaseModal open={modalOpen} setOpen={setModalOpen}>
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
        <span className="pr-2">{myModalTitle}</span>
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
            {type === TypeModal.PROMPT && isEdit ? (
              <Textarea
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
              />
            ) : type === TypeModal.PROMPT && !isEdit ? (
              <TextAreaContentView />
            ) : type !== TypeModal.PROMPT ? (
              <Textarea
                ref={ref}
                className="form-input h-full w-full rounded-lg focus-visible:ring-1"
                value={inputValue}
                onChange={(event) => {
                  setInputValue(event.target.value);
                }}
                placeholder="Type message here."
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
                          key={getRandomKeyByssmm() + index}
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
                              <span>
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
              onClick={() => {
                switch (myModalType) {
                  case TypeModal.TEXT:
                    setValue(inputValue);
                    setModalOpen(false);
                    break;
                  case TypeModal.PROMPT:
                    !inputValue || inputValue === ""
                      ? setModalOpen(false)
                      : validatePrompt(false);
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
