import { useContext, useRef, useState, useEffect } from "react";
import { PopUpContext } from "../../contexts/popUpContext";
import { darkContext } from "../../contexts/darkContext";
import { postValidatePrompt } from "../../controllers/API";
import { alertContext } from "../../contexts/alertContext";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "../../components/ui/dialog";
import { Button } from "../../components/ui/button";
import { Textarea } from "../../components/ui/textarea";
import {
  HIGHLIGH_CSS,
  PROMPT_DIALOG_SUBTITLE,
  TEXT_DIALOG_SUBTITLE,
} from "../../constants";
import { FileText } from "lucide-react";
import { APIClassType } from "../../types/api";
import {
  INVALID_CHARACTERS,
  TypeModal,
  classNames,
  getRandomKeyByssmm,
  regexHighlight,
  varHighlightHTML,
} from "../../utils";
import { Badge } from "../../components/ui/badge";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "../../components/ui/tooltip";
import ShadTooltip from "../../components/ShadTooltipComponent";
import { set } from "lodash";
import DOMPurify from "dompurify";

export default function GenericModal({
  field_name = "",
  value,
  setValue,
  buttonText,
  modalTitle,
  type,
  nodeClass,
  setNodeClass,
}: {
  field_name?: string;
  setValue: (value: string) => void;
  value: string;
  buttonText: string;
  modalTitle: string;
  type: number;
  nodeClass?: APIClassType;
  setNodeClass?: (Class: APIClassType) => void;
}) {
  const [myButtonText] = useState(buttonText);
  const [myModalTitle] = useState(modalTitle);
  const [myModalType] = useState(type);
  const [open, setOpen] = useState(true);
  const [inputValue, setInputValue] = useState(value);
  const [isEdit, setIsEdit] = useState(true);
  const [wordsHighlightInvalid, setWordsHighlightInvalid] = useState([]);
  const [wordsHighlight, setWordsHighlight] = useState([]);
  const { dark } = useContext(darkContext);
  const { setErrorData, setSuccessData } = useContext(alertContext);
  const { closePopUp, setCloseEdit } = useContext(PopUpContext);
  const ref = useRef();
  function setModalOpen(x: boolean) {
    setOpen(x);
    if (x === false) {
      setCloseEdit("generic");
      closePopUp();
    }
  }

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

    setWordsHighlightInvalid(invalid_chars);
    setWordsHighlight(filteredWordsHighlight);
  }

  useEffect(() => {
    if (type == TypeModal.PROMPT && inputValue && inputValue != "") {
      checkVariables(inputValue);
    }
  }, []);

  const coloredContent = (inputValue || "")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(regexHighlight, varHighlightHTML({ name: "$1" }))
    .replace(/\n/g, "<br />");

  const TextAreaContentView = () => {
    return (
      <div
        className={HIGHLIGH_CSS}
        dangerouslySetInnerHTML={{ __html: DOMPurify.sanitize(coloredContent) }}
        suppressContentEditableWarning={true}
        onClick={() => {
          setIsEdit(true);
        }}
      />
    );
  };

  function validatePrompt(closeModal: boolean) {
    postValidatePrompt(field_name, inputValue, nodeClass)
      .then((apiReturn) => {
        if (apiReturn.data) {
          setNodeClass(apiReturn.data.frontend_node);
          setModalOpen(closeModal);

          let inputVariables = apiReturn.data.input_variables;
          if (inputVariables.length === 0) {
            setIsEdit(true);
            setErrorData({
              title:
                "The template you are attempting to use does not contain any variables for data entry.",
            });
          } else {
            setIsEdit(false);
            setSuccessData({
              title: "Prompt is ready",
            });
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
        setIsEdit(true);
        return setErrorData({
          title: "There is something wrong with this prompt, please review it",
          list: [error.response.data.detail],
        });
      });
  }

  return (
    <Dialog open={true} onOpenChange={setModalOpen}>
      <DialogTrigger></DialogTrigger>
      <DialogContent className="min-w-[80vw]">
        <DialogHeader>
          <DialogTitle className="flex items-center">
            <span className="pr-2">{myModalTitle}</span>
            <FileText
              strokeWidth={1.5}
              className="h-6 w-6 pl-1 text-primary "
              aria-hidden="true"
            />
          </DialogTitle>
          <DialogDescription>
            {(() => {
              switch (myModalTitle) {
                case "Edit Text":
                  return TEXT_DIALOG_SUBTITLE;

                case "Edit Prompt":
                  return PROMPT_DIALOG_SUBTITLE;

                default:
                  return null;
              }
            })()}
          </DialogDescription>
        </DialogHeader>

        {type == TypeModal.PROMPT &&
          inputValue &&
          inputValue != "" &&
          wordsHighlight.length > 0 && (
            <>
              <div>
                <span className="">Variables: </span>
                {wordsHighlight.map((word, index) => (
                  <ShadTooltip
                    key={getRandomKeyByssmm() + index}
                    content={word.replace(/[{}]/g, "")}
                    asChild={false}
                    delayDuration={1500}
                  >
                    <Badge
                      key={index}
                      size="lg"
                      className="m-1 max-w-[40vw] cursor-default truncate p-2.5 text-sm"
                    >
                      <div className="relative bottom-[1px]">
                        <span>
                          {word.replace(/[{}]/g, "").length > 59
                            ? word.replace(/[{}]/g, "").slice(0, 56) + "..."
                            : word.replace(/[{}]/g, "")}
                        </span>
                      </div>
                    </Badge>
                  </ShadTooltip>
                ))}
              </div>
            </>
          )}

        <div
          className={classNames(
            !isEdit ? "rounded-lg border" : "",
            "flex h-[60vh] w-full"
          )}
        >
          {type == TypeModal.PROMPT && isEdit ? (
            <Textarea
              ref={ref}
              className="form-input h-full w-full rounded-lg border-gray-300 focus-visible:ring-1 dark:border-gray-700 dark:bg-gray-900 dark:text-white"
              value={inputValue}
              onBlur={() => {
                blur();
                setIsEdit(false);
              }}
              autoFocus
              onChange={(e) => {
                setInputValue(e.target.value);
                checkVariables(e.target.value);
              }}
              placeholder="Type message here."
            />
          ) : type == TypeModal.PROMPT && !isEdit ? (
            <TextAreaContentView />
          ) : type != TypeModal.PROMPT ? (
            <Textarea
              ref={ref}
              className="form-input h-full w-full rounded-lg border-gray-300 focus-visible:ring-1 dark:border-gray-700 dark:bg-gray-900 dark:text-white"
              value={inputValue}
              onChange={(e) => {
                setInputValue(e.target.value);
              }}
              placeholder="Type message here."
            />
          ) : (
            <></>
          )}
        </div>

        <DialogFooter>
          <Button
            className="mt-3"
            onClick={() => {
              switch (myModalType) {
                case 1:
                  setValue(inputValue);
                  setModalOpen(false);
                  break;
                case 2:
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
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
