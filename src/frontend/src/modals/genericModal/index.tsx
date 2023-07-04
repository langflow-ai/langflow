import { useContext, useRef, useState } from "react";
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
import { PROMPT_DIALOG_SUBTITLE, TEXT_DIALOG_SUBTITLE } from "../../constants";
import { FileText } from "lucide-react";
import { APIClassType } from "../../types/api";

export default function GenericModal({
  value,
  setValue,
  buttonText,
  modalTitle,
  type,
  nodeClass,
  setNodeClass,
}: {
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
  const [myValue, setMyValue] = useState(value);
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

  return (
    <Dialog open={true} onOpenChange={setModalOpen}>
      <DialogTrigger></DialogTrigger>
      <DialogContent className="lg:max-w-[700px]">
        <DialogHeader>
          <DialogTitle className="flex items-center">
            <span className="pr-2">{myModalTitle}</span>
            <FileText
            strokeWidth={1.5}
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

        <div className="mt-2 flex h-full w-full">
          <Textarea
            ref={ref}
            className=" h-[300px] w-full form-primary "
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
                  postValidatePrompt(myValue, nodeClass)
                    .then((apiReturn) => {
                      if (apiReturn.data) {
                        setNodeClass(apiReturn.data.frontend_node);
                        setModalOpen(false);

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
