// organize-imports-ignore
import { useContext, useEffect, useRef, useState } from "react";
import { PopUpContext } from "../../contexts/popUpContext";
import AceEditor from "react-ace";
import "ace-builds/src-noconflict/ext-language_tools";
import "ace-builds/src-noconflict/mode-python";
import "ace-builds/src-noconflict/theme-github";
import "ace-builds/src-noconflict/theme-twilight";
import "ace-builds/src-noconflict/ext-language_tools";
import "ace-builds/src-noconflict/ace";
// import "ace-builds/webpack-resolver";
import { TerminalSquare } from "lucide-react";
import { useContext, useState } from "react";
import AceEditor from "react-ace";
import { Button } from "../../components/ui/button";
import { CODE_PROMPT_DIALOG_SUBTITLE } from "../../constants";
import { alertContext } from "../../contexts/alertContext";
import { darkContext } from "../../contexts/darkContext";
import { postCustomComponent, postValidateCode } from "../../controllers/API";
import { APIClassType } from "../../types/api";
import {
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from "../../components/ui/tabs";

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
  const [code, setCode] = useState(value);
  const { dark } = useContext(darkContext);
  const { setErrorData, setSuccessData } = useContext(alertContext);
  const [activeTab, setActiveTab] = useState("0");
  const [error, setError] = useState<{
    detail: { error: string; traceback: string };
  }>(null);
  const { closePopUp, setCloseEdit } = useContext(PopUpContext);
  const { setErrorData, setSuccessData } = useContext(alertContext);

  function setModalOpen(x: boolean) {
    if (x === false) {
      setCloseEdit("codearea");
      closePopUp();
    }
  }
  console.log(dynamic);

  useEffect(() => {
    setValue(code);
  }, [code, setValue]);

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
          setErrorData({
            title:
              "There is something wrong with this code, please see the error on the errors tab",
          });
          console.log(err.response.data);
          setError(err.response.data);
        });
    }
    // axios.get("/api/v1/custom_component_error").catch((err) => {

    // })
  }
  const tabs = [{ name: "code" }, { name: "errors" }];

  return (
    <Dialog open={true} onOpenChange={setModalOpen}>
      <DialogTrigger></DialogTrigger>
      <DialogContent className="min-w-[80vw]">
        <DialogHeader>
          <DialogTitle className="flex items-center">
            <span className="pr-2">Edit Code</span>
            <TerminalSquare
              strokeWidth={1.5}
              className="h-6 w-6 pl-1 text-primary "
              aria-hidden="true"
            />
          </DialogTitle>
          <DialogDescription>{CODE_PROMPT_DIALOG_SUBTITLE}</DialogDescription>
        </DialogHeader>
        <Tabs
          defaultValue={"0"}
          className="h-full w-full overflow-hidden rounded-md border bg-muted text-center"
          onValueChange={(value) => setActiveTab(value)}
        >
          <div className="flex h-72 flex-col items-start px-2">
            <TabsList>
              {tabs.map((tab, index) => (
                <TabsTrigger
                  disabled={index === 1 && error?.detail.error === undefined}
                  key={index}
                  value={index.toString()}
                >
                  <span
                    className={
                      error?.detail.error !== undefined && index === 1
                        ? "text-destructive"
                        : ""
                    }
                  >
                    {tab.name}
                  </span>
                </TabsTrigger>
              ))}
            </TabsList>
            {tabs.map((tab, index) => (
              <TabsContent
                value={index.toString()}
                className="mt-1 h-full w-full overflow-hidden px-4 pb-4"
              >
                {tab.name === "code" ? (
                  <div className="h-full w-full">
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
                      className="h-full w-full rounded-lg border-[1px] border-gray-300 custom-scroll dark:border-gray-600"
                    />
                  </div>
                ) : (
                  <div className="flex h-full  w-full flex-col overflow-scroll bg-red-200 p-2 text-left custom-scroll">
                    <h1 className="text-lg text-red-600">
                      {error?.detail?.error}
                    </h1>
                    <span className="w-full border border-red-300"></span>
                    <div className="text-sm text-red-500">
                      {error?.detail?.traceback}
                    </div>
                  </div>
                )}
              </TabsContent>
            ))}
          </div>
        </Tabs>
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
