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
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "../../components/ui/dialog";
import { Button } from "../../components/ui/button";
import { EDIT_DIALOG_SUBTITLE } from "../../constants";

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
          data.node.template[t].type === "int")
    ).length
  );
  const [nodeValue, setNodeValue] = useState(true);
  const { closePopUp } = useContext(PopUpContext);
  const { types } = useContext(typesContext);
  const ref = useRef();
  const { save } = useContext(TabsContext);
  const [enabled, setEnabled] = useState(false);
  if (nodeLength == 0) {
    closePopUp();
  }

  function setModalOpen(x: boolean) {
    setOpen(x);
    if (x === false) {
      closePopUp();
    }
  }

  function changeAdvanced(node): void {
    Object.keys(data.node.template).filter((n, i) => {
      if (n === node.name) {
        data.node.template[n].advanced = !data.node.template[n].advanced;
      }
      return true;
    });
    setNodeValue(!nodeValue);
  }

  // console.log(data.node.template);

  return (
    <Dialog open={true} onOpenChange={setModalOpen}>
      <DialogTrigger></DialogTrigger>
      <DialogContent className="lg:max-w-[700px]">
        <DialogHeader>
          <DialogTitle className="flex items-center">
            <span className="pr-2">Edit Node</span>
            <PencilSquareIcon
              className="h-6 w-6 text-gray-800 pl-1 dark:text-white"
              aria-hidden="true"
            />
          </DialogTitle>
          <DialogDescription>
            {EDIT_DIALOG_SUBTITLE}
            <div className="flex pt-3">
              <VariableIcon className="w-5 h-5 pe-1 text-gray-700 stroke-2">
                &nbsp;
              </VariableIcon>
              <span className="text-sm font-semibold text-gray-800">
                Parameters
              </span>
            </div>
          </DialogDescription>
        </DialogHeader>

        <div className="flex w-full h-fit max-h-[415px]">
          <div
            className={classNames(
              "w-full rounded-lg bg-white dark:bg-gray-800 shadow",
              nodeLength > limitScrollFieldsModal
                ? "overflow-scroll overflow-x-hidden custom-scroll"
                : "overflow-hidden"
            )}
          >
            {nodeLength > 0 && (
              <div className="flex flex-col gap-5 h-fit">
                <Table className="table-fixed">
                  <TableHeader className="border-gray-200 text-gray-500 text-xs font-medium">
                    <TableRow>
                      <TableHead className="h-7 text-center">PARAM</TableHead>
                      <TableHead className="p-0 h-7 text-center">
                        VALUE
                      </TableHead>
                      <TableHead className="text-center h-7">SHOW</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody className="p-0">
                    {Object.keys(data.node.template)
                      .filter(
                        (t) =>
                          t.charAt(0) !== "_" &&
                          data.node.template[t].show &&
                          (data.node.template[t].type === "str" ||
                            data.node.template[t].type === "bool" ||
                            data.node.template[t].type === "float" ||
                            data.node.template[t].type === "code" ||
                            data.node.template[t].type === "prompt" ||
                            data.node.template[t].type === "file" ||
                            data.node.template[t].type === "int")
                      )
                      .map((n, i) => (
                        <TableRow key={i} className="h-8">
                          <TableCell className="p-0 text-center text-gray-900 text-xs dark:text-gray-300">
                            {data.node.template[n].name
                              ? data.node.template[n].name
                              : data.node.template[n].display_name}
                          </TableCell>
                          <TableCell className="p-0 text-center text-gray-900 text-xs w-[300px] dark:text-gray-300">
                            {data.node.template[n].type === "str" &&
                            !data.node.template[n].options ? (
                              <div className="mx-auto">
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
                                    editNode={true}
                                    value={data.node.template[n].value ?? ""}
                                    onChange={(t: string) => {
                                      data.node.template[n].value = t;
                                      save();
                                    }}
                                  />
                                ) : (
                                  <InputComponent
                                    editNode={true}
                                    disabled={false}
                                    password={
                                      data.node.template[n].password ?? false
                                    }
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
                                <ToggleShadComponent
                                  enabled={data.node.template[n].value}
                                  setEnabled={(e) => {
                                    data.node.template[n].value = e;
                                    setEnabled(e);
                                    save();
                                  }}
                                  disabled={false}
                                />
                              </div>
                            ) : data.node.template[n].type === "float" ? (
                              <div className="mx-auto">
                                <FloatComponent
                                  disabled={false}
                                  editNode={true}
                                  value={data.node.template[n].value ?? ""}
                                  onChange={(t) => {
                                    data.node.template[n].value = t;
                                    save();
                                  }}
                                />
                              </div>
                            ) : data.node.template[n].type === "str" &&
                              data.node.template[n].options ? (
                              <div className="mx-auto">
                                <Dropdown
                                  editNode={true}
                                  options={data.node.template[n].options}
                                  onSelect={(newValue) =>
                                    (data.node.template[n].value = newValue)
                                  }
                                  value={
                                    data.node.template[n].value ??
                                    "Choose an option"
                                  }
                                ></Dropdown>
                              </div>
                            ) : data.node.template[n].type === "int" ? (
                              <div className="mx-auto">
                                <IntComponent
                                  disabled={false}
                                  editNode={true}
                                  value={data.node.template[n].value ?? ""}
                                  onChange={(t) => {
                                    data.node.template[n].value = t;
                                    save();
                                  }}
                                />
                              </div>
                            ) : data.node.template[n].type === "file" ? (
                              <div className="mx-auto">
                                <InputFileComponent
                                  editNode={true}
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
                              <div className="mx-auto">
                                <PromptAreaComponent
                                  editNode={true}
                                  disabled={false}
                                  value={data.node.template[n].value ?? ""}
                                  onChange={(t: string) => {
                                    data.node.template[n].value = t;
                                    save();
                                  }}
                                />
                              </div>
                            ) : data.node.template[n].type === "code" ? (
                              <div className="mx-auto">
                                <CodeAreaComponent
                                  disabled={false}
                                  editNode={true}
                                  value={data.node.template[n].value ?? ""}
                                  onChange={(t: string) => {
                                    data.node.template[n].value = t;
                                    save();
                                  }}
                                />
                              </div>
                            ) : data.node.template[n].type === "Any" ? (
                              "-"
                            ) : (
                              <div className="hidden"></div>
                            )}
                          </TableCell>
                          <TableCell className="p-0 text-right">
                            <div className="items-center text-center">
                              <ToggleShadComponent
                                enabled={!data.node.template[n].advanced}
                                setEnabled={(e) =>
                                  changeAdvanced(data.node.template[n])
                                }
                                disabled={false}
                              />
                            </div>
                          </TableCell>
                        </TableRow>
                      ))}
                  </TableBody>
                </Table>
              </div>
            )}
          </div>
        </div>

        <DialogFooter>
          <Button
            className="mt-3"
            onClick={() => {
              setModalOpen(false);
            }}
            type="submit"
          >
            Save changes
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
