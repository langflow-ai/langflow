import { Dialog, Transition } from "@headlessui/react";
import {
  XMarkIcon,
  ArrowDownTrayIcon,
  DocumentDuplicateIcon,
  ComputerDesktopIcon,
} from "@heroicons/react/24/outline";
import { Fragment, useContext, useRef, useState } from "react";
import { alertContext } from "../../contexts/alertContext";
import { PopUpContext } from "../../contexts/popUpContext";
import { TabsContext } from "../../contexts/tabsContext";
import { removeApiKeys } from "../../utils";

export default function ExportModal() {
  const [open, setOpen] = useState(true);
  const { closePopUp } = useContext(PopUpContext);
  const ref = useRef();
  const { setErrorData } = useContext(alertContext);
  const { flows, tabIndex, updateFlow, downloadFlow, setDisableCopyPaste } =
    useContext(TabsContext);
  function setModalOpen(x: boolean) {
    setOpen(x);
    if (x === false) {
      setTimeout(() => {
        closePopUp();
      }, 300);
    }
  }
  const [checked, setChecked] = useState(true);
  const [name, setName] = useState(flows[tabIndex].name);
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
              <Dialog.Panel className="relative flex h-[600px] w-[700px] transform flex-col justify-between overflow-hidden rounded-lg bg-white text-left shadow-xl transition-all dark:bg-gray-800 sm:my-8">
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
                <div className="flex h-full w-full flex-col items-center justify-center">
                  <div className="z-10 flex w-full justify-center pb-4 shadow-sm">
                    <div className="mx-auto mt-4 flex h-12 w-12 flex-shrink-0 items-center justify-center rounded-full bg-blue-100 dark:bg-gray-900 sm:mx-0 sm:h-10 sm:w-10">
                      <ArrowDownTrayIcon
                        className="h-6 w-6 text-blue-600"
                        aria-hidden="true"
                      />
                    </div>
                    <div className="mt-4 text-center sm:ml-4 sm:text-left">
                      <Dialog.Title
                        as="h3"
                        className="text-lg font-medium leading-10 text-gray-900 dark:text-white"
                      >
                        Export as
                      </Dialog.Title>
                    </div>
                  </div>
                  <div className="flex h-full w-full flex-col items-start justify-start gap-16 bg-gray-200 p-4 pt-16 dark:bg-gray-900">
                    <div className="w-full">
                      <label
                        htmlFor="name"
                        className="mb-2 block font-medium text-gray-700 dark:text-white"
                      >
                        Name
                      </label>
                      <input
                        onChange={(event) => {
                          if (event.target.value != "") {
                            let newFlow = flows[tabIndex];
                            newFlow.name = event.target.value;
                            setName(event.target.value);
                            updateFlow(newFlow);
                          } else {
                            setName(event.target.value);
                          }
                        }}
                        type="text"
                        name="name"
                        value={name ?? null}
                        placeholder="File name"
                        id="name"
                        className="focus:border-blue block w-full rounded-md border-gray-300 px-3 py-2 text-gray-900 shadow-sm focus:border focus:border-blue-500 focus:outline-none focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-800 dark:text-gray-100 dark:focus:border-blue-500 dark:focus:ring-blue-500"
                        onBlur={() => {
                          setDisableCopyPaste(false);
                        }}
                        onFocus={() => {
                          setDisableCopyPaste(true);
                        }}
                      />
                    </div>
                    <div className="w-full">
                      <label
                        htmlFor="description"
                        className="mb-2 block font-medium text-gray-700 dark:text-white"
                      >
                        Description{" "}
                        <span className="text-sm text-gray-400">
                          {" "}
                          (optional)
                        </span>
                      </label>
                      <textarea
                        onBlur={() => {
                          setDisableCopyPaste(false);
                        }}
                        onFocus={() => {
                          setDisableCopyPaste(true);
                        }}
                        name="description"
                        id="description"
                        onChange={(event) => {
                          let newFlow = flows[tabIndex];
                          newFlow.description = event.target.value;
                          updateFlow(newFlow);
                        }}
                        value={flows[tabIndex].description ?? null}
                        placeholder="Flow description"
                        rows={3}
                        className=" focus:border-blue block w-full rounded-md border-gray-300 px-3 py-2 text-gray-900 shadow-sm focus:border focus:border-blue-500 focus:outline-none focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-800 dark:text-gray-100 dark:focus:border-blue-500 dark:focus:ring-blue-500"
                      ></textarea>
                    </div>

                    <div>
                      <label htmlFor="checkbox" className="flex items-center">
                        <input
                          onChange={(event) => {
                            setChecked(event.target.checked);
                          }}
                          checked={checked}
                          id="checkbox"
                          type="checkbox"
                          className="h-4 w-4 rounded border-gray-300 text-blue-600 dark:border-gray-600 dark:bg-gray-800 dark:focus:border-blue-500 dark:focus:ring-blue-500"
                          onBlur={() => {
                            setDisableCopyPaste(false);
                          }}
                          onFocus={() => {
                            setDisableCopyPaste(true);
                          }}
                        />
                        <span className="ml-2 font-medium text-gray-700 dark:text-white">
                          Save with my API keys
                        </span>
                      </label>
                    </div>
                    <div className="flex w-full justify-end">
                      <button
                        onClick={() => {
                          if (checked) downloadFlow(flows[tabIndex]);
                          else downloadFlow(removeApiKeys(flows[tabIndex]));
                        }}
                        className="rounded bg-blue-500 px-4 py-2 font-bold text-white hover:bg-blue-700"
                      >
                        Download Flow
                      </button>
                    </div>
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
