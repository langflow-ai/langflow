import { Dialog, Transition } from "@headlessui/react";
import {
  ChevronDoubleLeftIcon,
  ChevronDoubleRightIcon,
  PencilSquareIcon,
  XMarkIcon,
} from "@heroicons/react/24/outline";
import { Fragment, useContext, useEffect, useRef, useState } from "react";
import { PopUpContext } from "../../contexts/popUpContext";
import { NodeDataType } from "../../types/flow";
import { classNames, limitScrollFieldsModal, nodeIcons } from "../../utils";
import { typesContext } from "../../contexts/typesContext";
import {
  Table,
  TableBody,
  TableCaption,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "../../components/ui/table";
import { Switch } from "../../components/ui/switch";
import ToggleShadComponent from "../../components/toggleShadComponent";



export default function EditNodeModal({ data }: { data: NodeDataType }) {
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

  function changeAdvanced(node): void{
    Object.keys(data.node.template).filter((n, i) => {
      if (n === node.name) {
        data.node.template[n].advanced = !data.node.template[n].advanced;
      }
      return true;
    });
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
                      <PencilSquareIcon
                        className="h-6 w-6 text-blue-600"
                        aria-hidden="true"
                      />
                    </div>
                    <div className="mt-4 text-center sm:ml-4 sm:text-left">
                      <Dialog.Title
                        as="h3"
                        className="text-lg font-medium dark:text-white leading-10 text-gray-900"
                      >
                        Edit Node
                      </Dialog.Title>
                    </div>
                  </div>
                  <div className="h-full w-full bg-gray-200 dark:bg-gray-900 p-4 gap-4 flex flex-row justify-center items-center">
                    <div className="flex w-full h-full max-h-[445px]">
                      <div
                        className={classNames(
                          "w-full rounded-lg bg-white dark:bg-gray-800 shadow",
                          Object.keys(data.node.template).filter(
                            (t) =>
                              t.charAt(0) !== "_" &&
                              data.node.template[t].show &&
                              (data.node.template[t].type === "str" ||
                                data.node.template[t].type === "bool" ||
                                data.node.template[t].type === "float" ||
                                data.node.template[t].type === "code" ||
                                data.node.template[t].type === "prompt" ||
                                data.node.template[t].type === "file" ||
                                data.node.template[t].type === "Any" ||
                                data.node.template[t].type === "int")
                          ).length > limitScrollFieldsModal
                            ? "overflow-scroll overflow-x-hidden custom-scroll h-fit"
                            : "overflow-hidden h-fit"
                        )}
                      >
                        <div className="flex flex-col h-full gap-5 h-fit	">
                          <Table>
                            <TableHeader>
                              <TableRow>
                                <TableHead className="w-[80px]">
                                  Param
                                </TableHead>
                                <TableHead>Value</TableHead>
                                <TableHead>Show</TableHead>
                              </TableRow>
                            </TableHeader>
                            <TableBody>
                            { Object.keys(data.node.template).filter(
                                  (t) =>
                                    t.charAt(0) !== "_" &&
                                    data.node.template[t].show &&
                                    (data.node.template[t].type === "str" ||
                                      data.node.template[t].type === "bool" ||
                                      data.node.template[t].type === "float" ||
                                      data.node.template[t].type === "code" ||
                                      data.node.template[t].type === "prompt" ||
                                      data.node.template[t].type === "file" ||
                                      data.node.template[t].type === "Any" ||
                                      data.node.template[t].type === "int")
                                )
                                .map((n, i) => (
                                <TableRow key={i}>
                                  <TableCell className="font-medium">
                                  {data.node.template[n].name
                                        ? data.node.template[n].name
                                        : data.node.template[n].display_name}
                                  </TableCell>
                                  <TableCell>
                                  {data.node.template[n].value
                                        ? data.node.template[n].value
                                        : "-"}
                                  </TableCell>
                                  <TableCell>

                                  <div className="flex items-center space-x-2">
                                  <ToggleShadComponent 
                                  enabled={data.node.template[n].advanced}
                                  setEnabled={(e) => changeAdvanced(data.node.template[n])}
                                  disabled={false} />
                                </div>
                                  </TableCell>
                                </TableRow>
                              ))}
                            </TableBody>
                          </Table>
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
