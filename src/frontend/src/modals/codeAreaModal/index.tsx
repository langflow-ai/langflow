import "ace-builds/src-noconflict/ace";
import "ace-builds/src-noconflict/ext-language_tools";
import "ace-builds/src-noconflict/mode-python";
import "ace-builds/src-noconflict/theme-github";
import "ace-builds/src-noconflict/theme-twilight";
// import "ace-builds/webpack-resolver";
import { useEffect, useState } from "react";
import AceEditor from "react-ace";
import IconComponent from "../../components/genericIconComponent";
import { Button } from "../../components/ui/button";
import { Input } from "../../components/ui/input";
import {
  BUG_ALERT,
  CODE_ERROR_ALERT,
  CODE_SUCCESS_ALERT,
  FUNC_ERROR_ALERT,
  IMPORT_ERROR_ALERT,
} from "../../constants/alerts_constants";
import {
  CODE_PROMPT_DIALOG_SUBTITLE,
  EDIT_CODE_TITLE,
} from "../../constants/constants";
import { postCustomComponent, postValidateCode } from "../../controllers/API";
import useAlertStore from "../../stores/alertStore";
import { useDarkStore } from "../../stores/darkStore";
import { CodeErrorDataTypeAPI } from "../../types/api";
import { codeAreaModalPropsType } from "../../types/components";
import BaseModal from "../baseModal";

export default function CodeAreaModal({
  value,
  setValue,
  nodeClass,
  setNodeClass,
  children,
  dynamic,
  readonly = false,
  open: myOpen,
  setOpen: mySetOpen,
}: codeAreaModalPropsType): JSX.Element {
  const [code, setCode] = useState(value);
  const [open, setOpen] =
    mySetOpen !== undefined && myOpen !== undefined
      ? [myOpen, mySetOpen]
      : useState(false);
  const dark = useDarkStore((state) => state.dark);
  const [height, setHeight] = useState<string | null>(null);
  const setSuccessData = useAlertStore((state) => state.setSuccessData);
  const setErrorData = useAlertStore((state) => state.setErrorData);
  const [error, setError] = useState<{
    detail: CodeErrorDataTypeAPI;
  } | null>(null);

  useEffect(() => {
    // if nodeClass.template has more fields other than code and dynamic is true
    // do not run handleClick
    if (dynamic && Object.keys(nodeClass!.template).length > 2) {
      return;
    }
  }, []);

  function processNonDynamicField() {
    postValidateCode(code)
      .then((apiReturn) => {
        if (apiReturn.data) {
          let importsErrors = apiReturn.data.imports.errors;
          let funcErrors = apiReturn.data.function.errors;
          if (funcErrors.length === 0 && importsErrors.length === 0) {
            setSuccessData({
              title: CODE_SUCCESS_ALERT,
            });
            setOpen(false);
            setValue(code);
            // setValue(code);
          } else {
            if (funcErrors.length !== 0) {
              setErrorData({
                title: FUNC_ERROR_ALERT,
                list: funcErrors,
              });
            }
            if (importsErrors.length !== 0) {
              setErrorData({
                title: IMPORT_ERROR_ALERT,
                list: importsErrors,
              });
            }
          }
        } else {
          setErrorData({
            title: BUG_ALERT,
          });
        }
      })
      .catch((_) => {
        setErrorData({
          title: CODE_ERROR_ALERT,
        });
      });
  }

  function processDynamicField() {
    postCustomComponent(code, nodeClass!)
      .then((apiReturn) => {
        const { data, type } = apiReturn.data;
        if (data && type) {
          setNodeClass(data, code, type);
          setError({ detail: { error: undefined, traceback: undefined } });
          setOpen(false);
        }
      })
      .catch((err) => {
        setError(err.response.data);
      });
  }

  function processCode() {
    if (!dynamic) {
      processNonDynamicField();
    } else {
      processDynamicField();
    }
  }

  function handleClick() {
    processCode();
  }

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

  useEffect(() => {
    setCode(value);
  }, [value, open]);

  return (
    <BaseModal open={open} setOpen={setOpen}>
      <BaseModal.Trigger>{children}</BaseModal.Trigger>
      <BaseModal.Header description={CODE_PROMPT_DIALOG_SUBTITLE}>
        <span className="pr-2"> {EDIT_CODE_TITLE} </span>
        <IconComponent
          name="prompts"
          className="h-6 w-6 pl-1 text-primary"
          aria-hidden="true"
        />
      </BaseModal.Header>
      <BaseModal.Content>
        <Input
          value={code}
          readOnly
          className="absolute left-[500%] top-[500%]"
          id="codeValue"
        />
        <div className="flex h-full w-full flex-col transition-all">
          <div className="h-full w-full">
            <AceEditor
              readOnly={readonly}
              value={code}
              mode="python"
              setOptions={{ fontFamily: "monospace" }}
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
              "whitespace-break-spaces transition-all delay-500" +
              (error?.detail?.error !== undefined ? "h-2/6" : "h-0")
            }
          >
            <div className="mt-5 h-full max-h-[10rem] w-full overflow-y-auto overflow-x-clip text-left custom-scroll">
              <h1 className="text-lg text-error">{error?.detail?.error}</h1>
              <div className="ml-2 mt-2 w-full text-sm text-destructive word-break-break-word">
                <span className="w-full word-break-break-word">
                  {error?.detail?.traceback}
                </span>
              </div>
            </div>
          </div>
          <div className="flex h-fit w-full justify-end">
            <Button
              className="mt-3"
              onClick={handleClick}
              type="submit"
              id="checkAndSaveBtn"
              disabled={readonly}
            >
              Check & Save
            </Button>
          </div>
        </div>
      </BaseModal.Content>
    </BaseModal>
  );
}
