import { Dialog, Transition } from "@headlessui/react";
import {
  XMarkIcon,
  ArrowDownTrayIcon,
  DocumentDuplicateIcon,
  ComputerDesktopIcon,
  ArrowUpTrayIcon,
  ArrowLeftIcon,
} from "@heroicons/react/24/outline";
import { Fragment, useContext, useRef, useState } from "react";
import { PopUpContext } from "../../contexts/popUpContext";
import { TabsContext } from "../../contexts/tabsContext";
import ButtonBox from "./buttonBox";
import { getExamples } from "../../controllers/API";
import { error } from "console";
import { alertContext } from "../../contexts/alertContext";
import LoadingComponent from "../../components/loadingComponent";
import { FlowType } from "../../types/flow";
import { classNames, snakeToSpaces, toNormalCase } from "../../utils";
import ToggleComponent from "../../components/toggleComponent";

export default function ImportModal() {
  const [open, setOpen] = useState(true);
  const { setErrorData } = useContext(alertContext);
  const { closePopUp } = useContext(PopUpContext);
  const ref = useRef();
  const [showExamples, setShowExamples] = useState(false);
  const [loadingExamples, setLoadingExamples] = useState(false);
  const [examples, setExamples] = useState<FlowType[]>([]);
  const { uploadFlow, addFlow } = useContext(TabsContext);
  const [newTab, setNewTab] = useState(true);
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
    <Transition.Root show={open} appear={true} as={Fragment}>
      <Dialog
        as="div"
        className="relative z-10"
        onClose={setModalOpen}
        initialFocus={ref}
      >
        <Transition.Child
          as={Fragment}
          enter="ease-out duration-300"
          enterFrom="opacity-0"
          enterTo="opacity-100"
          leave="ease-in duration-200"
          leaveFrom="opacity-100"
          leaveTo="opacity-0"
        >
          <div className="fixed inset-0 bg-gray-500 bg-opacity-75 transition-opacity dark:bg-gray-600 dark:bg-opacity-75" />
        </Transition.Child>

        <div className="fixed inset-0 z-10 overflow-y-auto">
          <div className="flex h-full items-end justify-center p-4 text-center sm:items-center sm:p-0">
            <Transition.Child
              as={Fragment}
              enter="ease-out duration-300"
              enterFrom="opacity-0 translate-y-4 sm:translate-y-0 sm:scale-95"
              enterTo="opacity-100 translate-y-0 sm:scale-100"
              leave="ease-in duration-200"
              leaveFrom="opacity-100 translate-y-0 sm:scale-100"
              leaveTo="opacity-0 translate-y-4 sm:translate-y-0 sm:scale-95"
            >
              <Dialog.Panel className="relative flex h-[600px] w-[776px] transform flex-col justify-between overflow-hidden rounded-lg bg-white text-left shadow-xl transition-all dark:bg-gray-800 sm:my-8">
                <div className=" absolute right-0 top-0 z-50 hidden pr-4 pt-4 sm:block">
                  <button
                    type="button"
                    className="rounded-md text-gray-400 hover:text-gray-500"
                    onClick={() => {
                      setModalOpen(false);
                    }}
                  >
                    <span className="sr-only">Close</span>
                    <XMarkIcon className="h-6 w-6" aria-hidden="true" />
                  </button>
                </div>
                {showExamples && (
                  <>
                    <div className="absolute left-0 top-2 z-50 hidden pl-4 pt-4 sm:block">
                      <button
                        type="button"
                        className="rounded-md text-gray-400 hover:text-gray-500 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2"
                        onClick={() => {
                          setShowExamples(false);
                        }}
                      >
                        <span className="sr-only">Close</span>
                        <ArrowLeftIcon className="h-6 w-6" aria-hidden="true" />
                      </button>
                    </div>
                  </>
                )}
                <div className="flex h-full w-full flex-col items-center justify-center">
                  <div className="z-10 flex w-full justify-center pb-4 shadow-sm">
                    <div className="mx-auto mt-4 flex h-12 w-12 flex-shrink-0 items-center justify-center rounded-full bg-blue-100 dark:bg-gray-900 sm:mx-0 sm:h-10 sm:w-10">
                      <ArrowUpTrayIcon
                        className="h-6 w-6 text-blue-600"
                        aria-hidden="true"
                      />
                    </div>
                    <div className="mt-4 text-center sm:ml-4 sm:text-left">
                      <Dialog.Title
                        as="h3"
                        className="text-lg font-medium leading-10 text-gray-900 dark:text-white"
                      >
                        {showExamples ? "Select an Example" : "Import Flow"}
                      </Dialog.Title>
                    </div>
                  </div>
                  <div
                    className={classNames(
                      "h-full w-full gap-4 overflow-y-auto bg-gray-200 scrollbar-hide dark:bg-gray-900",
                      showExamples && !loadingExamples
                        ? "start flex flex-row flex-wrap items-start justify-start overflow-auto p-9"
                        : "flex flex-row items-center justify-center p-4"
                    )}
                  >
                    {!showExamples && (
                      <div className="flex h-full w-full items-center justify-evenly">
                        <ButtonBox
                          size="big"
                          bgColor="bg-emerald-500 dark:bg-emerald-500/75"
                          description="Prebuilt Examples"
                          icon={
                            <DocumentDuplicateIcon className="h-10 w-10 flex-shrink-0" />
                          }
                          onClick={() => {
                            setShowExamples(true);
                            handleExamples();
                          }}
                          textColor="text-emerald-500 dark:text-emerald-500/75"
                          title="Examples"
                        ></ButtonBox>
                        <ButtonBox
                          size="big"
                          bgColor="bg-blue-500 dark:bg-blue-500/75"
                          description="Import from Local"
                          icon={
                            <ComputerDesktopIcon className="h-10 w-10 flex-shrink-0" />
                          }
                          onClick={() => {
                            uploadFlow(newTab);
                            setModalOpen(false);
                          }}
                          textColor="text-blue-500 dark:text-blue-500/75"
                          title="Local File"
                        ></ButtonBox>
                      </div>
                    )}
                    {showExamples && loadingExamples && (
                      <div className="flex items-center justify-center align-middle">
                        <LoadingComponent remSize={30} />
                      </div>
                    )}
                    {showExamples &&
                      !loadingExamples &&
                      examples.map((example, index) => {
                        return (
                          <div id="index">
                            {" "}
                            <ButtonBox
                              key={index}
                              size="small"
                              bgColor="bg-emerald-500 dark:bg-emerald-500/75"
                              description={
                                example.description ?? "Prebuilt Examples"
                              }
                              icon={
                                <DocumentDuplicateIcon className="h-6 w-6 flex-shrink-0" />
                              }
                              onClick={() => {
                                addFlow(example, newTab);
                                setModalOpen(false);
                              }}
                              textColor="text-emerald-500 dark:text-emerald-500/75"
                              title={example.name}
                            ></ButtonBox>
                          </div>
                        );
                      })}
                  </div>
                  <div className="flex h-20 w-full items-center justify-between bg-white px-8 dark:bg-gray-800">
                    <div className="flex items-center justify-center gap-4 text-gray-600 dark:text-gray-300">
                      <ToggleComponent
                        enabled={newTab}
                        setEnabled={setNewTab}
                        disabled={false}
                      />
                      Open in a new tab
                    </div>
                    <a
                      href="https://github.com/logspace-ai/langflow_examples"
                      target="_blank"
                      className="flex items-center justify-center text-gray-600 dark:text-gray-300"
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
                      <span className="ml-2 ">LangFlow Examples</span>
                    </a>
                  </div>
                </div>
              </Dialog.Panel>
            </Transition.Child>
          </div>
        </div>
      </Dialog>
    </Transition.Root>
  );
}
