import { Dialog, Transition } from "@headlessui/react";
import { XMarkIcon, CommandLineIcon } from "@heroicons/react/24/outline";
import { Fragment, useContext, useRef, useState } from "react";
import { PopUpContext } from "../../contexts/popUpContext";
import AceEditor from "react-ace";
import "ace-builds/src-noconflict/mode-python";
import "ace-builds/src-noconflict/theme-github";
import "ace-builds/src-noconflict/theme-twilight";
import "ace-builds/src-noconflict/ext-language_tools";
// import "ace-builds/webpack-resolver";
import { darkContext } from "../../contexts/darkContext";
import { checkCode } from "../../controllers/API";
import { alertContext } from "../../contexts/alertContext";
import { TabsContext } from "../../contexts/tabsContext";
export default function CodeAreaModal({
  value,
  setValue,
}: {
  setValue: (value: string) => void;
  value: string;
}) {
  const [open, setOpen] = useState(true);
  const [code, setCode] = useState(value);
  const { dark } = useContext(darkContext);
  const { setErrorData, setSuccessData } = useContext(alertContext);
  const { closePopUp } = useContext(PopUpContext);
  const ref = useRef();
  function setModalOpen(x: boolean) {
    setOpen(x);
    if (x === false) {
      setTimeout(() => {
        closePopUp();
      }, 300);
    }
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
          <div className="fixed inset-0 bg-gray-500 dark:bg-gray-600 dark:bg-opacity-75 bg-opacity-75 transition-opacity" />
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
              <Dialog.Panel className="relative flex flex-col justify-between transform h-[600px] overflow-hidden rounded-lg bg-white dark:bg-gray-800 text-left shadow-xl transition-all sm:my-8 w-[700px]">
                <div className=" z-50 absolute top-0 right-0 hidden pt-4 pr-4 sm:block">
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
                <div className="h-full w-full flex flex-col justify-center items-center">
                  <div className="flex w-full pb-4 z-10 justify-center shadow-sm">
                    <div className="mx-auto mt-4 flex h-12 w-12 flex-shrink-0 items-center justify-center rounded-full bg-blue-100 dark:bg-gray-900 sm:mx-0 sm:h-10 sm:w-10">
                      <CommandLineIcon
                        className="h-6 w-6 text-blue-600"
                        aria-hidden="true"
                      />
                    </div>
                    <div className="mt-4 text-center sm:ml-4 sm:text-left">
                      <Dialog.Title
                        as="h3"
                        className="text-lg font-medium dark:text-white leading-10 text-gray-900"
                      >
                        Edit Code
                      </Dialog.Title>
                    </div>
                  </div>
                  <div className="h-full w-full bg-gray-200 overflow-auto dark:bg-gray-900 p-4 gap-4 flex flex-row justify-center items-center">
                    <div className="flex h-full w-full">
                      <div className="overflow-hidden px-4 py-5 sm:p-6 w-full h-full rounded-lg bg-white dark:bg-gray-800 shadow">
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
                          className="h-full w-full rounded-lg"
                        />
                      </div>
                    </div>
                  </div>
                  <div className="bg-gray-200 dark:bg-gray-900 w-full pb-3 flex flex-row-reverse px-4">
                    <button
                      type="button"
                      className="inline-flex w-full justify-center rounded-md border border-transparent bg-indigo-600 px-4 py-2 text-base font-medium text-white shadow-sm hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2 sm:ml-3 sm:w-auto sm:text-sm"
                      onClick={() => {
                        checkCode(code)
                          .then((apiReturn) => {
                            if (apiReturn.data) {
                              let importsErrors = apiReturn.data.imports.errors;
                              let funcErrors = apiReturn.data.function.errors;
                              if (
                                funcErrors.length === 0 &&
                                importsErrors.length === 0
                              ) {
                                setSuccessData({
                                  title: "Code is ready to run",
                                });
                                setModalOpen(false);
                                setValue(code);
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
                          .catch((_) =>
                            setErrorData({
                              title:
                                "There is something wrong with this code, please review it",
                            })
                          );
                      }}
                    >
                      Check & Save
                    </button>
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
