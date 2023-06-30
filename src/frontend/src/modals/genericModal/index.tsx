import { Fragment, useContext, useRef, useState } from "react";
import { PopUpContext } from "../../contexts/popUpContext";
import { darkContext } from "../../contexts/darkContext";
import { checkPrompt } from "../../controllers/API";
import { alertContext } from "../../contexts/alertContext";
import { TypeModal } from "../../utils";
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
import { PROMPT_DIALOG_SUBTITLE, TEXT_DIALOG_SUBTITLE } from "../../constants";
import { FileText } from "lucide-react";
import { useEffect } from "react";

export default function GenericModal({
  value,
  setValue,
  buttonText,
  modalTitle,
  type,
}: {
  setValue: (value: string) => void;
  value: string;
  buttonText: string;
  modalTitle: string;
  type: number;
}) {
  const [myButtonText] = useState(buttonText);
  const [myModalTitle] = useState(modalTitle);
  const [myModalType] = useState(type);
  const [open, setOpen] = useState(true);
  const [myValue, setMyValue] = useState(value);
  const [highlight, setHighlight] = useState("");
  const [wordsHighlight, setWordsHighlight] = useState([]);
  const { dark } = useContext(darkContext);
  const { setErrorData, setSuccessData } = useContext(alertContext);
  const { closePopUp } = useContext(PopUpContext);
  const ref = useRef();
  function setModalOpen(x: boolean) {
    setOpen(x);
    if (x === false) {
      closePopUp();
    }
  }

  const INVALID_CHARACTERS = [
    " ",
    ",",
    ".",
    ":",
    ";",
    "!",
    "?",
    "/",
    "\\",
    "(",
    ")",
    "[",
    "]",
  ];
  

  function checkVariables(){
    const regex = /\{([^{}]+)\}/g;
    const matches = [];
    let match;
    while ((match = regex.exec(myValue))) {
      matches.push(`{${match[1]}}`);
    }

    let invalid_chars = [];
    let fixed_variables = [];
    let input_variables = matches; // Replace this with your input list of variables
    for (let variable of input_variables) {
      let new_var = variable;
      for (let char of INVALID_CHARACTERS) {
        if (variable.includes(char)) {
          invalid_chars.push(char);
          new_var = new_var.replace(new RegExp(char, "g"), "");
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
    console.log(fixed_variables);
    console.log(invalid_chars);
    setWordsHighlight(matches);
  }
  

  useEffect(() => {
    if(type == TypeModal.PROMPT && myValue && myValue != ""){
      checkVariables();
    }
  }, []);




  return (
    <Dialog open={true} onOpenChange={setModalOpen}>
      <DialogTrigger></DialogTrigger>
      <DialogContent className="lg:max-w-[700px]">
        <DialogHeader>
          <DialogTitle className="flex items-center">
            <span className="pr-2">{myModalTitle}</span>
            <FileText
              className="h-6 w-6 text-primary pl-1 "
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

        <div className="h-full w-full mt-2">

          <Textarea
            ref={ref}
            className="form-input h-[300px] w-full rounded-lg border-ring focus-visible:ring-1"
            value={myValue}
            onChange={(e) => {
              setMyValue(e.target.value);
              setValue(e.target.value);
              checkVariables();
            }}
            placeholder="Type message here."
          />
        </div>

        <DialogFooter>
          <Button
            className="mt-3"
            onClick={() => {
              switch (myModalType) {
                case 1:
                  setModalOpen(false);
                  break;
                case 2:
                  checkPrompt(myValue)
                    .then((apiReturn) => {
                      if (apiReturn.data) {
                        let inputVariables = apiReturn.data.input_variables;
                        if (inputVariables.length === 0) {
                          setErrorData({
                            title:
                              "The template you are attempting to use does not contain any variables for data entry.",
                          });
                        } else {
                          setSuccessData({
                            title: "Prompt is ready",
                          });
                          setModalOpen(false);
                          setValue(myValue);
                        }
                      } else {
                        setErrorData({
                          title: "Something went wrong, please try again",
                        });
                      }
                    })
                    .catch((error) => {
                      return setErrorData({
                        title:
                          "There is something wrong with this prompt, please review it",
                        list: [error.response.data.detail],
                      });
                    });
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

