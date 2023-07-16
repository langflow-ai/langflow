// organize-imports-ignore
import { useContext, useEffect, useRef, useState } from "react";
import { PopUpContext } from "../../contexts/popUpContext";
import "ace-builds/src-noconflict/ace";
import { darkContext } from "../../contexts/darkContext";
import { postCustomComponent, postValidateCode } from "../../controllers/API";
import { alertContext } from "../../contexts/alertContext";
import { Button } from "../../components/ui/button";
import { CODE_PROMPT_DIALOG_SUBTITLE } from "../../constants";
import { APIClassType } from "../../types/api";
import { DialogTitle } from "@radix-ui/react-dialog";
import { TerminalSquare } from "lucide-react";
import AceEditor from "react-ace";
import "ace-builds/src-noconflict/mode-python";
import "ace-builds/src-noconflict/theme-github";
import "ace-builds/src-noconflict/theme-twilight";
import "ace-builds/src-noconflict/ext-language_tools";
import "ace-builds/src-noconflict/ace";
import BaseModal from "../baseModal";

export default function CodeAreaModal({
  value,
  setValue,
  nodeClass,
  setNodeClass,
  dynamic,
}: {
  setValue: (value: string) => void;
  value: string;
  nodeClass: APIClassType;
  setNodeClass: (Class: APIClassType) => void;
  dynamic?: boolean;
}) {
  const [open, setOpen] = useState(true);
  const [code, setCode] = useState(value);
  const [loading, setLoading] = useState(false);
  const { dark } = useContext(darkContext);
  const { setErrorData, setSuccessData } = useContext(alertContext);
  const [height, setHeight] = useState(null);
  const [error, setError] = useState<{
    detail: { error: string; traceback: string };
  }>(null);
  const { closePopUp, setCloseEdit } = useContext(PopUpContext);
  function setModalOpen(x: boolean) {
    setOpen(x);
    if (x === false) {
      setTimeout(() => {
        setCloseEdit("editcode");
        closePopUp();
      }, 300);
    }
  }
  useEffect(() => {
    setValue(code);
  }, [code, setValue]);

  useEffect(() => {
    handleClick();
  }, [])

  function handleClick() {
    setLoading(true);
    if (!dynamic) {
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
    } else {
      postCustomComponent(code, nodeClass)
        .then((apiReturn) => {
          const { data } = apiReturn;
          if (data) {
            setNodeClass(data);
            setModalOpen(false);
          }
        })
        .catch((err) => {
          setError(err.response.data);
        });
    }
  }

  /// use effect to update ace editor on error to handle right scroll
  useEffect(() => {
    // Function to be executed after the state changes
    const delayedFunction = setTimeout(() => {
      if (error?.detail.error !== undefined) {
        //trigger to update the height, does not really apply any height
        setHeight("90%");
      }
      //600 to happen after the transition of 500ms
    }, 600);

    // Cleanup function to clear the timeout if the component unmounts or the state changes again
    return () => {
      clearTimeout(delayedFunction);
    };
  }, [error, setHeight]);

  return (
    <BaseModal open={true} setOpen={setOpen}>
      <BaseModal.Header description={CODE_PROMPT_DIALOG_SUBTITLE}>
        <DialogTitle className="flex items-center">
          <span className="pr-2">Edit Code</span>
          <TerminalSquare
            strokeWidth={1.5}
            className="h-6 w-6 pl-1 text-primary "
            aria-hidden="true"
          />
        </DialogTitle>
      </BaseModal.Header>
      <BaseModal.Content>
        <div className="flex h-full w-full flex-col transition-all">
          <div className="h-full w-full">
            <AceEditor
              value={code}
              mode="python"
              height={height ?? "100%"}
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
              className="h-full w-full rounded-lg border-[1px] border-gray-300 custom-scroll dark:border-gray-600"
            />
          </div>
          <div
            className={
              "w-full transition-all delay-500 " +
              (error?.detail.error !== undefined ? "h-2/6" : "h-0")
            }
          >
            <div className="mt-1 h-full w-full overflow-y-auto overflow-x-clip text-left custom-scroll">
              <h1 className="text-lg text-destructive">
                {error?.detail?.error}
              </h1>
              <div className="ml-2 w-full break-all text-sm text-status-red">
                <pre className="w-full whitespace-pre-wrap break-all">
                  {error?.detail?.traceback}
                </pre>
              </div>
            </div>
          </div>
          <div className="flex h-fit w-full justify-end">
            <Button className="mt-3" onClick={handleClick} type="submit">
              Check & Save
            </Button>
          </div>
        </div>
      </BaseModal.Content>
    </BaseModal>
  );
}
