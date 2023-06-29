import { useContext, useEffect, useRef, useState } from "react";
import { PopUpContext } from "../../contexts/popUpContext";
import { NodeDataType } from "../../types/flow";
import { classNames, limitScrollFieldsModal } from "../../utils";
import { typesContext } from "../../contexts/typesContext";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "../../components/ui/table";
import ToggleShadComponent from "../../components/toggleShadComponent";
import InputListComponent from "../../components/inputListComponent";
import TextAreaComponent from "../../components/textAreaComponent";
import InputComponent from "../../components/inputComponent";
import FloatComponent from "../../components/floatComponent";
import Dropdown from "../../components/dropdownComponent";
import IntComponent from "../../components/intComponent";
import InputFileComponent from "../../components/inputFileComponent";
import PromptAreaComponent from "../../components/promptComponent";
import CodeAreaComponent from "../../components/codeAreaComponent";
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
import { Badge } from "../../components/ui/badge";
import { Variable } from "lucide-react";

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
  const [nodeValue, setNodeValue] = useState(null);
  const { closePopUp } = useContext(PopUpContext);
  const { types } = useContext(typesContext);
  const ref = useRef();
  const [enabled, setEnabled] = useState(null);
  if (nodeLength == 0) {
    closePopUp();
  }

  function setModalOpen(x: boolean) {
    setOpen(x);
    if (x === false) {
      closePopUp();
    }
  }

  useEffect(() => {}, [closePopUp, data.node.template]);

  function changeAdvanced(node): void {
    Object.keys(data.node.template).filter((n, i) => {
      if (n === node.name) {
        data.node.template[n].advanced = !data.node.template[n].advanced;
      }
      return true;
    });
    setNodeValue(!nodeValue);
  }

  return (
    <Dialog open={true} onOpenChange={setModalOpen}>
      <DialogTrigger asChild></DialogTrigger>
      <DialogContent className="lg:max-w-[700px] ">
        <DialogHeader>
          <DialogTitle className="flex items-center">
            <span className="pr-2">{data.type}</span>
            <Badge variant="secondary">ID: {data.id}</Badge>
          </DialogTitle>
          <DialogDescription>
            {data.node?.description}
            <div className="flex pt-4">
              <Variable className="w-5 h-5 pe-1 text-gray-700 stroke-2 dark:text-slate-200"></Variable>
              <span className="text-sm font-semibold text-gray-800 dark:text-white">
                Parameters
              </span>
            </div>
          </DialogDescription>
        </DialogHeader>

        <div className="flex w-full max-h-[350px] h-fit">
          <div
            className={classNames(
              "w-full rounded-lg bg-white dark:bg-gray-800 border-[1px] border-gray-200",
              nodeLength > limitScrollFieldsModal
                ? "overflow-scroll overflow-x-hidden custom-scroll"
                : "overflow-hidden"
            )}
          >
            {nodeLength > 0 && (
              <div className="flex flex-col gap-5 h-fit">
                <Table className="table-fixed bg-muted outline-1">
                  <TableHeader className="border-gray-200 text-gray-500 text-xs font-medium h-10">
                    <TableRow className="dark:border-b-muted">
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
                        <TableRow key={i} className="h-10 dark:border-b-muted">
                          <TableCell className="p-0 text-center text-gray-900 dark:text-gray-300 text-sm">
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
                                    editNode={true}
                                    disabled={false}
                                    value={
                                      !data.node.template[n].value ||
                                      data.node.template[n].value === ""
                                        ? [""]
                                        : data.node.template[n].value
                                    }
                                    onChange={(t: string[]) => {
                                      data.node.template[n].value = t;
                                    }}
                                  />
                                ) : data.node.template[n].multiline ? (
                                  <TextAreaComponent
                                    disabled={false}
                                    editNode={true}
                                    value={data.node.template[n].value ?? ""}
                                    onChange={(t: string) => {
                                      data.node.template[n].value = t;
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
                                  }}
                                  size="small"
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
                                  }}
                                />
                              </div>
                            ) : data.node.template[n].type === "str" &&
                              data.node.template[n].options ? (
                              <div className="mx-auto">
                                <Dropdown
                                  numberOfOptions={nodeLength}
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
                                size="small"
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
            Save Changes
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
