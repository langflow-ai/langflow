import { Dialog, Transition } from "@headlessui/react";
import { XMarkIcon, DocumentTextIcon } from "@heroicons/react/24/outline";
import { Fragment, useContext, useRef, useState } from "react";
import { PopUpContext } from "../../contexts/popUpContext";
import { darkContext } from "../../contexts/darkContext";
import { checkPrompt } from "../../controllers/API";
import { alertContext } from "../../contexts/alertContext";
export default function PromptAreaModal({
  value,
  setValue,
}: {
  setValue: (value: string) => void;
  value: string;
}) {
  const [open, setOpen] = useState(true);
  const [myValue, setMyValue] = useState(value);
  const { dark } = useContext(darkContext);
  const { setErrorData, setSuccessData } = useContext(alertContext);
  const { closePopUp, setCloseEdit } = useContext(PopUpContext);
  const ref = useRef();
  function setModalOpen(x: boolean) {
    setOpen(x);
    if (x === false) {
      setTimeout(() => {
        setCloseEdit("prompt");
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
          <div className="fixed inset-0 bg-ring   bg-opacity-75 transition-opacity" />
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
              <Dialog.Panel className="relative flex h-[600px] w-[700px] transform flex-col justify-between overflow-hidden rounded-lg bg-background text-left shadow-xl transition-all sm:my-8">
                <div className=" absolute right-0 top-0 z-50 hidden pr-4 pt-4 sm:block">
                  <button
                    type="button"
                    className="rounded-md text-ring hover:text-ring"
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
                    <div className="mx-auto mt-4 flex h-12 w-12 flex-shrink-0 items-center justify-center rounded-full bg-almost-light-blue sm:mx-0 sm:h-10 sm:w-10">
                      <DocumentTextIcon
                        className="h-6 w-6 text-almost-medium-blue"
                        aria-hidden="true"
                      />
                    </div>
                    <div className="mt-4 text-center sm:ml-4 sm:text-left">
                      <Dialog.Title
                        as="h3"
                        className="text-lg font-medium leading-10 text-foreground"
                      >
                        Edit Prompt
                      </Dialog.Title>
                    </div>
                  </div>
                  <div className="flex h-full w-full flex-row items-center justify-center gap-4 overflow-auto bg-accent p-4">
                    <div className="flex h-full w-full">
                      <div className="h-full w-full overflow-hidden rounded-lg bg-background px-4 py-5 shadow sm:p-6">
                        <textarea
                          ref={ref}
                          className="form-input h-full w-full rounded-lg border-ring"
                          value={myValue}
                          onChange={(e) => {
                            setMyValue(e.target.value);
                            setValue(e.target.value);
                          }}
                        />
                      </div>
                    </div>
                  </div>
                  <div className="flex w-full flex-row-reverse bg-input px-4 pb-3">
                    <button
                      type="button"
                      className="inline-flex w-full justify-center rounded-md border border-transparent px-4 py-2 text-base font-medium text-background shadow-sm hover:bg-ring focus:outline-none focus:ring-1 focus:ring-ring focus:ring-offset-1 sm:ml-3 sm:w-auto sm:text-sm"
                      onClick={() => {
                        checkPrompt(myValue)
                          .then((apiReturn) => {
                            if (apiReturn.data) {
                              let inputVariables =
                                apiReturn.data.input_variables;
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
