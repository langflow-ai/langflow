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
import { VariableIcon } from "@heroicons/react/24/outline";
import InputListComponent from "../../components/inputListComponent";
import TextAreaComponent from "../../components/textAreaComponent";
import InputComponent from "../../components/inputComponent";
import ToggleComponent from "../../components/toggleComponent";
import FloatComponent from "../../components/floatComponent";
import Dropdown from "../../components/dropdownComponent";
import IntComponent from "../../components/intComponent";
import InputFileComponent from "../../components/inputFileComponent";
import PromptAreaComponent from "../../components/promptComponent";
import CodeAreaComponent from "../../components/codeAreaComponent";
import { TabsContext } from "../../contexts/tabsContext";



export default function EditNodeModal({ data }: { data: NodeDataType }) {
  const [open, setOpen] = useState(true);
  const [nodeLength, setNodeLength] = useState(
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
    ).length
  );
  const [nodeValue, setNodeValue] = useState(true);
  const { closePopUp } = useContext(PopUpContext);
  const { types } = useContext(typesContext);
  const ref = useRef();
  const { save } = useContext(TabsContext);
  const [enabled, setEnabled] = useState(
    false
  );
  if(nodeLength == 0){
    closePopUp();
  }

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
    setNodeValue(!nodeValue)
  }

  console.log(data.node.template);
  

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
              <Dialog.Panel className="relative flex flex-col justify-between transform overflow-hidden rounded-lg bg-white dark:bg-gray-800 text-left shadow-xl transition-all sm:my-8 w-[700px]">
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
                  <div className="h-full w-full bg-gray-200 dark:bg-gray-900 p-4 pt-0 gap-4 justify-center items-center">
                  <div className="py-3 flex items-center">
                    <VariableIcon  className="w-5 h-5 pe-1 text-orange-500 stroke-2">&nbsp;</VariableIcon>
                  <span className="text-sm font-semibold text-gray-800">Variables</span>

                  </div>

                    <div className="flex w-full h-fit max-h-[415px]">

                      <div
                        className={classNames(
                          "w-full rounded-lg bg-white dark:bg-gray-800 shadow",
                          nodeLength > limitScrollFieldsModal
                          ? "overflow-scroll overflow-x-hidden custom-scroll"
                          : "overflow-hidden"
                        )}
                      >
                        {
                         nodeLength > 0 &&
                          <div className="flex flex-col gap-5 h-fit">
                          <Table>
                            <TableHeader className="border-gray-200 text-gray-500 text-xs font-medium">
                              <TableRow>
                                <TableHead className="h-7 text-center">
                                  PARAM
                                </TableHead>
                                <TableHead className="p-0 h-7 text-center">VALUE</TableHead>
                                <TableHead className="text-center h-7">SHOW</TableHead>
                              </TableRow>
                            </TableHeader>
                            <TableBody className="p-0">
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
                                <TableRow key={i} className="h-8">
                                  <TableCell className="p-0 text-center text-gray-900 text-xs">
                                  {data.node.template[n].name
                                        ? data.node.template[n].name
                                        : data.node.template[n].display_name}
                                  </TableCell>
                                  <TableCell className="p-0 text-center text-gray-900 text-xs w-[300px]">

      {data.node.template[n].type === "str" && !data.node.template[n].options ? (
        <div className="w-1/2">
          {data.node.template[n].list ? (
            <InputListComponent
              disabled={false}
              value={
                !data.node.template[n].value ||
                data.node.template[n].value === ""
                  ? [""]
                  : data.node.template[n].value
              }
              onChange={(t: string[]) => {
                data.node.template[n].value = t;
                save();
              }}
            />
          ) : data.node.template[n].multiline ? (
            <TextAreaComponent
              disabled={false}
              value={data.node.template[n].value ?? ""}
              onChange={(t: string) => {
                data.node.template[n].value = t;
                save();
              }}
            />
          ) : (
            <InputComponent
              disabled={false}
              password={data.node.template[n].password ?? false}
              value={data.node.template[n].value ?? ""}
              onChange={(t) => {
                data.node.template[n].value = t;
                save();
              }}
            />
          )}
        </div>
      ) : data.node.template[n].type === "bool" ? (
        <div className="ml-auto">
          {" "}
          <ToggleComponent
            disabled={false}
            enabled={enabled}
            setEnabled={(t) => {
              data.node.template[n].value = t;
              setEnabled(t);
              save();
            }}
          />
        </div>
      ) : data.node.template[n].type === "float" ? (
        <div className="w-1/2">
          <FloatComponent
            disabled={false}
            value={data.node.template[n].value ?? ""}
            onChange={(t) => {
              data.node.template[n].value = t;
              save();
            }}
          />
        </div>
      ) : data.node.template[n].type === "str" && data.node.template[n].options ? (
        <div className="w-1/2">
          <Dropdown
            options={data.node.template[n].options}
            onSelect={(newValue) => (data.node.template[n].value = newValue)}
            value={data.node.template[n].value ?? "Choose an option"}
          ></Dropdown>
        </div>
      ) : data.node.template[n].type === "int" ? (
        <div className="w-1/2">
          <IntComponent
            disabled={false}
            value={data.node.template[n].value ?? ""}
            onChange={(t) => {
              data.node.template[n].value = t;
              save();
            }}
          />
        </div>
      ) : data.node.template[n].type === "file" ? (
        <div className="w-1/2">
          <InputFileComponent
            disabled={false}
            value={data.node.template[n].value ?? ""}
            onChange={(t: string) => {
              data.node.template[n].value = t;
            }}
            fileTypes={data.node.template[n].fileTypes}
            suffixes={data.node.template[n].suffixes}
            onFileChange={(t: string) => {
              data.node.template[n].content = t;
              save();
            }}
          ></InputFileComponent>
        </div>
      ) : data.node.template[n].type === "prompt" ? (
        <div className="w-1/2">
          <PromptAreaComponent
            disabled={false}
            value={data.node.template[n].value ?? ""}
            onChange={(t: string) => {
              data.node.template[n].value = t;
              save();
            }}
          />
        </div>
      ) : data.node.template[n].type === "code" ? (
        <div className="w-1/2">
          <CodeAreaComponent
            disabled={false}
            value={data.node.template[n].value ?? ""}
            onChange={(t: string) => {
              data.node.template[n].value = t;
              save();
            }}
          />
        </div>
      ) : (
        <div className="hidden"></div>
      )}


{/* 
                                  {data.node.template[n].value
                                        ? data.node.template[n].value
                                        : "-"} */}

                                  </TableCell>
                                  <TableCell className="p-0 text-right">

                                  <div className="items-center text-center">
                                  <ToggleShadComponent 
                                  enabled={!data.node.template[n].advanced}
                                  setEnabled={(e) => changeAdvanced(data.node.template[n])}
                                  disabled={false} />
                                </div>
                                  </TableCell>
                                </TableRow>
                              ))}
                            </TableBody>
                          </Table>
                        </div>}
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
