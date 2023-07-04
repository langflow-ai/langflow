import { useContext, useRef, useState } from "react";
import { PopUpContext } from "../../contexts/popUpContext";
import AceEditor from "react-ace";
import "ace-builds/src-noconflict/mode-python";
import "ace-builds/src-noconflict/theme-github";
import "ace-builds/src-noconflict/theme-twilight";
import "ace-builds/src-noconflict/ext-language_tools";
// import "ace-builds/webpack-resolver";
import { darkContext } from "../../contexts/darkContext";
import { postCustomComponent, postValidateCode } from "../../controllers/API";
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
import { CODE_PROMPT_DIALOG_SUBTITLE } from "../../constants";
import { TerminalSquare } from "lucide-react";
import { APIClassType } from "../../types/api";

export default function CodeAreaModal({
  value,
  setValue,
  nodeClass,
  setNodeClass,
}: {
  setValue: (value: string) => void;
  value: string;
  nodeClass: APIClassType;
  setNodeClass: (Class: APIClassType) => void;
}) {
  const [open, setOpen] = useState(true);
  const [code, setCode] = useState(value);
  const [loading, setLoading] = useState(false);
  const { dark } = useContext(darkContext);
  const { setErrorData, setSuccessData } = useContext(alertContext);
  const { closePopUp, setCloseEdit } = useContext(PopUpContext);
  const ref = useRef();
  function setModalOpen(x: boolean) {
    setOpen(x);
    if (x === false) {
      setTimeout(() => {
        setCloseEdit("editcode");
        closePopUp();
      }, 300);
    }
  }

  function handleClick() {
    setLoading(true);
    postValidateCode(code)
      .then((apiReturn) => {
        setLoading(false);
        if (apiReturn.data) {
          let importsErrors = apiReturn.data.imports.errors;
          let funcErrors = apiReturn.data.function.errors;
          if (funcErrors.length === 0 && importsErrors.length === 0) {
            setSuccessData({
              title: "Code is ready to run",
            });
            // setValue(code);
          } else {
            if (funcErrors.length !== 0) {
              setErrorData({
                title: "There is an error in your function",
                list: funcErrors,
              });
            }
            if (importsErrors.length !== 0) {
              setErrorData({
                title: "There is an error in your imports",
                list: importsErrors,
              });
            }
          }
        } else {
          setErrorData({
            title: "Something went wrong, please try again",
          });
        }
      })
      .catch((_) => {
        setLoading(false);
        setErrorData({
          title: "There is something wrong with this code, please review it",
        });
      });
    postCustomComponent(code, nodeClass).then((apiReturn) => {
      const data = apiReturn.data;
      if (data) {
        setNodeClass(data);
        setModalOpen(false);
      }
    });
  }

  return (
    <Dialog open={true} onOpenChange={setModalOpen}>
      <DialogTrigger></DialogTrigger>
      <DialogContent className="h-[500px] lg:max-w-[700px]">
        <DialogHeader>
          <DialogTitle className="flex items-center">
            <span className="pr-2">Edit Code</span>
            <TerminalSquare
            strokeWidth={1.5}
              className="h-6 w-6 text-primary pl-1 "
              aria-hidden="true"
            />
          </DialogTitle>
          <DialogDescription>{CODE_PROMPT_DIALOG_SUBTITLE}</DialogDescription>
        </DialogHeader>

        <div className="mt-2 flex h-full w-full">
          <AceEditor
            value={code}
            mode="python"
            highlightActiveLine={true}
            showPrintMargin={false}
            fontSize={14}
            showGutter
            enableLiveAutocompletion
            theme={dark ? "twilight" : "github"}
            name="CodeEditor"
            onChange={(value) => {
              setCode(value);
            }}
            className="h-[300px] w-full rounded-lg border-[1px] border-ring custom-scroll "
          />
        </div>

        <DialogFooter>
          <Button className="mt-3" onClick={handleClick} type="submit">
            {/* {loading?(<Loading/>):'Check & Save'} */}
            Check & Save
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
