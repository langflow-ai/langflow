import { Dialog, Transition } from "@headlessui/react";
import { XMarkIcon } from "@heroicons/react/24/outline";
import { Fragment, useContext, useRef, useState } from "react";
import { PopUpContext } from "../../contexts/popUpContext";
import { NodeDataType } from "../../types/flow";
import {
  classNames,
  limitScrollFieldsModal,
  nodeColors,
  nodeIcons,
  toNormalCase,
  toTitleCase,
} from "../../utils";
import { typesContext } from "../../contexts/typesContext";
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
  const Icon = nodeIcons[types[data.type]];
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
                    <Icon
                      className="w-10 mt-4 h-10 p-1 rounded"
                      style={{
                        color:
                          nodeColors[types[data.type]] ?? nodeColors.unknown,
                      }}
                    />
                    <div className="mt-4 text-center sm:ml-4 sm:text-left">
                      <Dialog.Title
                        as="h3"
                        className="text-lg font-medium dark:text-white leading-10 text-gray-900"
                      >
                        {data.type}
                      </Dialog.Title>
                    </div>
                  </div>
                  <div className="h-full w-full bg-gray-200 dark:bg-gray-900 p-4 gap-4 flex flex-row justify-center items-center">
                    <div className="flex w-full h-[445px]">
                      <div
                        className={classNames(
                          "px-4 sm:p-4 w-full rounded-lg bg-white dark:bg-gray-800 shadow",
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
                        <div className="flex flex-col h-full gap-5">
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
                  <div className="bg-gray-200 dark:bg-gray-900 w-full pb-3 flex flex-row-reverse px-4">
                    <button
                      type="button"
                      className="inline-flex w-full justify-center rounded-md border border-transparent bg-indigo-600 px-4 py-2 text-base font-medium text-white shadow-sm hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2 sm:ml-3 sm:w-auto sm:text-sm"
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
