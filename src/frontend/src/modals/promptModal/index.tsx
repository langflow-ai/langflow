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
          <div className="node-modal-div" />
        </Transition.Child>

        <div className="node-modal-dialog-arrangement">
          <div className="node-modal-dialog-div">
            <Transition.Child
              as={Fragment}
              enter="ease-out duration-300"
              enterFrom="opacity-0 translate-y-4 sm:translate-y-0 sm:scale-95"
              enterTo="opacity-100 translate-y-0 sm:scale-100"
              leave="ease-in duration-200"
              leaveFrom="opacity-100 translate-y-0 sm:scale-100"
              leaveTo="opacity-0 translate-y-4 sm:translate-y-0 sm:scale-95"
            >
              <Dialog.Panel className="node-modal-dialog-panel">
                <div className=" node-modal-dialog-panel-div ">
                  <button
                    type="button"
                    className="node-modal-dialog-button"
                    onClick={() => {
                      setModalOpen(false);
                    }}
                  >
                    <span className="sr-only">Close</span>
                    <XMarkIcon className="h-6 w-6" aria-hidden="true" />
                  </button>
                </div>
                <div className="node-modal-dialog-icon-div">
                  <div className="node-modal-icon-arrangement">
                    <div className="prompt-modal-icon-box">
                      <DocumentTextIcon
                        className="prompt-modal-icon"
                        aria-hidden="true"
                      />
                    </div>
                    <div className="node-modal-title-div ">
                      <Dialog.Title
                        as="h3"
                        className="node-modal-title"
                      >
                        Edit Prompt
                      </Dialog.Title>
                    </div>
                  </div>
                  <div className="prompt-modal-txtarea-arrangement">
                    <div className="flex-max-width h-full">
                      <div className="prompt-modal-txtarea-box">
                        <textarea
                          ref={ref}
                          className="prompt-modal-txtarea"
                          value={myValue}
                          onChange={(e) => {
                            setMyValue(e.target.value);
                            setValue(e.target.value);
                          }}
                        />
                      </div>
                    </div>
                  </div>
                  <div className="node-modal-button-box">
                    <button
                      type="button"
                      className="node-modal-button"
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
