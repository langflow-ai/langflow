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

  return (
    <Dialog open={true} onOpenChange={setModalOpen}>
      <DialogTrigger></DialogTrigger>
      <DialogContent className="lg:max-w-[700px]">
        <DialogHeader>
          <DialogTitle className="flex items-center">
            <span className="pr-2">{myModalTitle}</span>
            <FileText
              className="h-6 w-6 text-gray-800 pl-1 dark:text-white"
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

        <div className="flex h-full w-full mt-2">
          <Textarea
            ref={ref}
            className="form-input h-[300px] w-full rounded-lg border-gray-300 dark:border-gray-700 dark:bg-gray-900 dark:text-white focus-visible:ring-1"
            value={myValue}
            onChange={(e) => {
              setMyValue(e.target.value);
              setValue(e.target.value);
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
