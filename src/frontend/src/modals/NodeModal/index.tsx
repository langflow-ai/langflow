import { Dialog, Transition } from "@headlessui/react";
import { X } from "lucide-react";
import { Fragment, useContext, useRef, useState } from "react";
import { PopUpContext } from "../../contexts/popUpContext";
import { typesContext } from "../../contexts/typesContext";
import { NodeDataType } from "../../types/flow";
import {
  classNames,
  limitScrollFieldsModal,
  nodeColors,
  nodeIconsLucide,
  toTitleCase,
} from "../../utils";
import ModalField from "./components/ModalField";

export default function NodeModal({ data }: { data: NodeDataType }) {
  const [open, setOpen] = useState(true);
  const { closePopUp } = useContext(PopUpContext);
  const { types } = useContext(typesContext);
  const ref = useRef();
  function setModalOpen(x: boolean) {
    setOpen(x);
    if (x === false) {
      setTimeout(() => {
        closePopUp();
      }, 300);
    }
  }
  // any to avoid type conflict
  const Icon: any = nodeIconsLucide[types[data.type]];
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
                    <X className="h-6 w-6" aria-hidden="true" />
                  </button>
                </div>
                <div className="node-modal-dialog-icon-div">
                  <div className="node-modal-icon-arrangement">
                    <Icon
                      strokeWidth={1.5}
                      className="node-modal-icon"
                      style={{
                        color:
                          nodeColors[types[data.type]] ?? nodeColors.unknown,
                      }}
                    />
                    <div className="node-modal-title-div">
                      <Dialog.Title as="h3" className="node-modal-title">
                        {data.type}
                      </Dialog.Title>
                    </div>
                  </div>
                  <div className="node-modal-template-div">
                    <div className="flex-max-width h-[445px]">
                      <div
                        className={classNames(
                          "node-modal-template",
                          Object.keys(data.node.template).filter(
                            (t) =>
                              t.charAt(0) !== "_" &&
                              data.node.template[t].advanced &&
                              data.node.template[t].show
                          ).length > limitScrollFieldsModal
                            ? "overflow-scroll overflow-x-hidden custom-scroll"
                            : "overflow-hidden"
                        )}
                      >
                        <div className="node-modal-template-column">
                          {Object.keys(data.node.template)
                            .filter(
                              (t) =>
                                t.charAt(0) !== "_" &&
                                data.node.template[t].advanced &&
                                data.node.template[t].show
                            )
                            .map((t: string, idx) => {
                              return (
                                <ModalField
                                  key={idx}
                                  data={data}
                                  title={
                                    data.node.template[t].display_name
                                      ? data.node.template[t].display_name
                                      : data.node.template[t].name
                                      ? toTitleCase(data.node.template[t].name)
                                      : toTitleCase(t)
                                  }
                                  required={data.node.template[t].required}
                                  id={
                                    data.node.template[t].type +
                                    "|" +
                                    t +
                                    "|" +
                                    data.id
                                  }
                                  name={t}
                                  type={data.node.template[t].type}
                                  index={idx}
                                />
                              );
                            })}
                        </div>
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
                      Done
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
