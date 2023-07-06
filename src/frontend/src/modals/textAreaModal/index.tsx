import { Dialog, Transition } from "@headlessui/react";
import {
  XMarkIcon,
  ClipboardDocumentListIcon,
} from "@heroicons/react/24/outline";
import { Fragment, useContext, useRef, useState } from "react";
import { PopUpContext } from "../../contexts/popUpContext";

export default function TextAreaModal({
  value,
  setValue,
}: {
  setValue: (value: string) => void;
  value: string | string[];
}) {
  const [open, setOpen] = useState(true);
  const [myValue, setMyValue] = useState(value);
  const { closePopUp, setCloseEdit } = useContext(PopUpContext);
  const ref = useRef();
  function setModalOpen(x: boolean) {
    setOpen(x);
    if (x === false) {
      setTimeout(() => {
        setCloseEdit("textarea");
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
                <div className=" node-modal-dialog-panel-div">
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
                      <ClipboardDocumentListIcon
                        className="prompt-modal-icon"
                        aria-hidden="true"
                      />
                    </div>
                    <div className="node-modal-title-div">
                      <Dialog.Title
                        as="h3"
                        className="node-modal-title"
                      >
                        Edit text
                      </Dialog.Title>
                    </div>
                  </div>
                  <div className="txtarea-modal-arrangement">
                    <div className="flex h-full w-full">
                      <div className="txtarea-modal-box">
                        <textarea
                          ref={ref}
                          className="txtarea-modal-input"
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
                        setModalOpen(false);
                      }}
                    >
                      Finish editing
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
