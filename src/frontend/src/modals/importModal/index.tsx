import {
  ArrowLeftIcon,
  ArrowUpTrayIcon,
  ComputerDesktopIcon,
  DocumentDuplicateIcon,
} from "@heroicons/react/24/outline";
import { useContext, useRef, useState } from "react";
import LoadingComponent from "../../components/loadingComponent";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "../../components/ui/dialog";
import { IMPORT_DIALOG_SUBTITLE } from "../../constants";
import { alertContext } from "../../contexts/alertContext";
import { PopUpContext } from "../../contexts/popUpContext";
import { TabsContext } from "../../contexts/tabsContext";
import { getExamples } from "../../controllers/API";
import { FlowType } from "../../types/flow";
import { classNames } from "../../utils";
import ButtonBox from "./buttonBox";

export default function ImportModal() {
  const [open, setOpen] = useState(true);
  const { setErrorData } = useContext(alertContext);
  const { closePopUp } = useContext(PopUpContext);
  const ref = useRef();
  const [showExamples, setShowExamples] = useState(false);
  const [loadingExamples, setLoadingExamples] = useState(false);
  const [examples, setExamples] = useState<FlowType[]>([]);
  const { uploadFlow, addFlow } = useContext(TabsContext);
  function setModalOpen(x: boolean) {
    setOpen(x);
    if (x === false) {
      setTimeout(() => {
        closePopUp();
      }, 300);
    }
  }

  function handleExamples() {
    setLoadingExamples(true);
    getExamples()
      .then((result) => {
        setLoadingExamples(false);
        setExamples(result);
      })
      .catch((error) =>
        setErrorData({
          title: "there was an error loading examples, please try again",
          list: [error.message],
        })
      );
  }

  return (
    <Dialog open={true} onOpenChange={setModalOpen}>
      <DialogTrigger></DialogTrigger>
      <DialogContent
        className={classNames(
          showExamples
            ? "h-[600px] lg:max-w-[650px]"
            : "h-[450px] lg:max-w-[650px]"
        )}
      >
        <DialogHeader>
          <DialogTitle className="flex items-center">
            {showExamples && (
              <>
                <div className="dialog-header-modal-div">
                  <button
                    type="button"
                    className="dialog-header-modal-button disabled:pointer-events-none data-[state=open]:bg-accent data-[state=open]:text-muted-foreground"
                    onClick={() => {
                      setShowExamples(false);
                    }}
                  >
                    <ArrowLeftIcon
                      className="ml-1 h-5 w-5 text-foreground"
                      aria-hidden="true"
                    />
                  </button>
                </div>
              </>
            )}

            <span className={classNames(showExamples ? "pl-8 pr-2" : "pr-2")}>
              {showExamples ? "Select an example" : "Import"}
            </span>
            <ArrowUpTrayIcon
              className="ml-1 h-5 w-5 text-foreground"
              aria-hidden="true"
            />
          </DialogTitle>
          <DialogDescription>{IMPORT_DIALOG_SUBTITLE}</DialogDescription>
        </DialogHeader>

        <div
          className={classNames(
            "dialog-modal-examples-div",
            showExamples && !loadingExamples
              ? "dialog-modal-example-true"
              : "dialog-modal-example-false"
          )}
        >
          {!showExamples && (
            <div className="dialog-modal-button-box-div">
              <ButtonBox
                size="big"
                bgColor="bg-medium-emerald "
                description="Prebuilt Examples"
                icon={<DocumentDuplicateIcon className="document-icon" />}
                onClick={() => {
                  setShowExamples(true);
                  handleExamples();
                }}
                textColor="text-medium-emerald "
                title="Examples"
              ></ButtonBox>
              <ButtonBox
                size="big"
                bgColor="bg-almost-dark-blue "
                description="Import from Local"
                icon={<ComputerDesktopIcon className="document-icon" />}
                onClick={() => {
                  uploadFlow();
                  setModalOpen(false);
                }}
                textColor="text-almost-dark-blue "
                title="Local File"
              ></ButtonBox>
            </div>
          )}
          {showExamples && loadingExamples && (
            <div className="loading-component-div">
              <LoadingComponent remSize={30} />
            </div>
          )}
          {showExamples &&
            !loadingExamples &&
            examples.map((example, index) => {
              return (
                <div key={example.name} className="m-2">
                  {" "}
                  <ButtonBox
                    size="small"
                    bgColor="bg-medium-emerald "
                    description={example.description ?? "Prebuilt Examples"}
                    icon={
                      <DocumentDuplicateIcon
                        strokeWidth={1.5}
                        className="h-6 w-6 flex-shrink-0"
                      />
                    }
                    onClick={() => {
                      addFlow(example, false);
                      setModalOpen(false);
                    }}
                    textColor="text-medium-emerald "
                    title={example.name}
                  ></ButtonBox>
                </div>
              );
            })}
        </div>

        <DialogFooter>
          <div className="dialog-modal-footer">
            <a
              href="https://github.com/logspace-ai/langflow_examples"
              target="_blank"
              className="dialog-modal-footer-link "
              rel="noreferrer"
            >
              <svg
                width="24"
                viewBox="0 0 98 96"
                xmlns="http://www.w3.org/2000/svg"
              >
                <path
                  fill-rule="evenodd"
                  clip-rule="evenodd"
                  d="M48.854 0C21.839 0 0 22 0 49.217c0 21.756 13.993 40.172 33.405 46.69 2.427.49 3.316-1.059 3.316-2.362 0-1.141-.08-5.052-.08-9.127-13.59 2.934-16.42-5.867-16.42-5.867-2.184-5.704-5.42-7.17-5.42-7.17-4.448-3.015.324-3.015.324-3.015 4.934.326 7.523 5.052 7.523 5.052 4.367 7.496 11.404 5.378 14.235 4.074.404-3.178 1.699-5.378 3.074-6.6-10.839-1.141-22.243-5.378-22.243-24.283 0-5.378 1.94-9.778 5.014-13.2-.485-1.222-2.184-6.275.486-13.038 0 0 4.125-1.304 13.426 5.052a46.97 46.97 0 0 1 12.214-1.63c4.125 0 8.33.571 12.213 1.63 9.302-6.356 13.427-5.052 13.427-5.052 2.67 6.763.97 11.816.485 13.038 3.155 3.422 5.015 7.822 5.015 13.2 0 18.905-11.404 23.06-22.324 24.283 1.78 1.548 3.316 4.481 3.316 9.126 0 6.6-.08 11.897-.08 13.526 0 1.304.89 2.853 3.316 2.364 19.412-6.52 33.405-24.935 33.405-46.691C97.707 22 75.788 0 48.854 0z"
                  fill="currentColor"
                />
              </svg>
              <span className="ml-2 ">Langflow Examples</span>
            </a>
          </div>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
