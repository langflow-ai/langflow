import { usePostValidateCode } from "@/controllers/API/queries/nodes/use-post-validate-code";
import { usePostValidateComponentCode } from "@/controllers/API/queries/nodes/use-post-validate-component-code";
import useFlowStore from "@/stores/flowStore";
import "ace-builds/src-noconflict/ace";
import "ace-builds/src-noconflict/ext-language_tools";
import "ace-builds/src-noconflict/ext-searchbox";
import "ace-builds/src-noconflict/mode-python";
import "ace-builds/src-noconflict/theme-github";
import "ace-builds/src-noconflict/theme-twilight";
import { useEffect, useRef, useState } from "react";
import AceEditor from "react-ace";
import ReactAce from "react-ace/lib/ace";
import IconComponent from "../../components/common/genericIconComponent";
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
import useAlertStore from "../../stores/alertStore";
import { useDarkStore } from "../../stores/darkStore";
import { CodeErrorDataTypeAPI } from "../../types/api";
import { codeAreaModalPropsType } from "../../types/components";
import BaseModal from "../baseModal";
import ConfirmationModal from "../confirmationModal";

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
  componentId,
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
  const [openConfirmation, setOpenConfirmation] = useState(false);
  const codeRef = useRef<ReactAce | null>(null);
  const { mutate } = usePostValidateCode();
  const [error, setError] = useState<{
    detail: CodeErrorDataTypeAPI;
  } | null>(null);

  const { mutate: validateComponentCode } = usePostValidateComponentCode();

  useEffect(() => {
    // if nodeClass.template has more fields other than code and dynamic is true
    // do not run handleClick
    if (dynamic && Object.keys(nodeClass!.template).length > 2) {
      return;
    }
  }, []);

  function processNonDynamicField() {
    mutate(
      { code },
      {
        onSuccess: (apiReturn) => {
          if (apiReturn) {
            let importsErrors = apiReturn.imports.errors;
            let funcErrors = apiReturn.function.errors;
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
        },
        onError: (error) => {
          setErrorData({
            title: CODE_ERROR_ALERT,
            list: [error.response.data.detail],
          });
        },
      },
    );
  }

  function processDynamicField() {
    validateComponentCode(
      { code, frontend_node: nodeClass! },
      {
        onSuccess: ({ data, type }) => {
          if (data && type) {
            setValue(code);
            setNodeClass(data, type);
            setError({ detail: { error: undefined, traceback: undefined } });
            setOpen(false);
          }
        },
        onError: (error) => {
          setError(error.response.data);
        },
      },
    );
  }

  function processCode() {
    if (!dynamic) {
      processNonDynamicField();
    } else {
      processDynamicField();
    }
  }

  useEffect(() => {
    // Function to be executed after the state changes
    const delayedFunction = setTimeout(() => {
      if (error?.detail?.error !== undefined) {
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
    if (!openConfirmation) {
      codeRef.current?.editor.focus();
    }
  }, [openConfirmation]);

  useEffect(() => {
    setCode(value);
  }, [value, open]);

  return (
    <BaseModal
      onEscapeKeyDown={(e) => {
        e.preventDefault();
        if (code === value) {
          setOpen(false);
        } else {
          if (
            !(
              codeRef.current?.editor.completer &&
              "popup" in codeRef.current?.editor.completer &&
              codeRef.current?.editor.completer.popup &&
              codeRef.current?.editor.completer.popup.isOpen
            )
          ) {
            setOpenConfirmation(true);
          }
        }
      }}
      open={open}
      setOpen={setOpen}
      size="x-large"
    >
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
              ref={codeRef}
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
              className="h-full min-w-full rounded-lg border-[1px] border-gray-300 custom-scroll dark:border-gray-600"
            />
          </div>
          <div
            className={
              "whitespace-break-spaces transition-all delay-500" +
              (error?.detail?.error !== undefined ? "h-2/6" : "h-0")
            }
          >
            <div className="mt-5 h-full max-h-[10rem] w-full overflow-y-auto overflow-x-clip text-left custom-scroll">
              <h1
                data-testid="title_error_code_modal"
                className="text-lg text-error"
              >
                {error?.detail?.error}
              </h1>
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
              onClick={processCode}
              type="submit"
              id="checkAndSaveBtn"
              disabled={readonly}
            >
              Check & Save
            </Button>
          </div>
        </div>
        <ConfirmationModal
          onClose={() => {
            setOpenConfirmation(false);
          }}
          onEscapeKeyDown={(e) => {
            e.stopPropagation();
            setOpenConfirmation(false);
          }}
          size="x-small"
          icon="AlertTriangle"
          confirmationText="Check & Save"
          cancelText="Discard Changes"
          open={openConfirmation}
          onCancel={() => setOpen(false)}
          onConfirm={() => {
            processCode();
            setOpenConfirmation(false);
          }}
          title="Caution"
        >
          <ConfirmationModal.Content>
            <p>Are you sure you want to exit without saving your changes?</p>
          </ConfirmationModal.Content>
        </ConfirmationModal>
      </BaseModal.Content>
    </BaseModal>
  );
}
