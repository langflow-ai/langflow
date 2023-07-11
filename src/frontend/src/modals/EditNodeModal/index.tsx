import { Variable } from "lucide-react";
import { useContext, useRef, useState } from "react";
import CodeAreaComponent from "../../components/codeAreaComponent";
import Dropdown from "../../components/dropdownComponent";
import FloatComponent from "../../components/floatComponent";
import InputComponent from "../../components/inputComponent";
import InputFileComponent from "../../components/inputFileComponent";
import InputListComponent from "../../components/inputListComponent";
import IntComponent from "../../components/intComponent";
import PromptAreaComponent from "../../components/promptComponent";
import TextAreaComponent from "../../components/textAreaComponent";
import ToggleShadComponent from "../../components/toggleShadComponent";
import { Badge } from "../../components/ui/badge";
import { Button } from "../../components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "../../components/ui/dialog";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "../../components/ui/table";
import { PopUpContext } from "../../contexts/popUpContext";
import { TabsContext } from "../../contexts/tabsContext";
import { typesContext } from "../../contexts/typesContext";
import { NodeDataType } from "../../types/flow";
import { classNames, limitScrollFieldsModal } from "../../utils";

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
  const { setTabsState, tabId } = useContext(TabsContext);
  const { reactFlowInstance } = useContext(typesContext);

  let disabled =
    reactFlowInstance?.getEdges().some((e) => e.targetHandle === data.id) ??
    false;
  if (nodeLength == 0) {
    closePopUp();
  }

  function setModalOpen(x: boolean) {
    setOpen(x);
    if (x === false) {
      closePopUp();
    }
  }

  function changeAdvanced(node) {
    Object.keys(data.node.template).map((n, i) => {
      if (n === node.name) {
        data.node.template[n].advanced = !data.node.template[n].advanced;
      }
      return n;
    });
    setNodeValue(!nodeValue);
  }

  const handleOnNewValue = (newValue: any, name) => {
    data.node.template[name].value = newValue;
    // Set state to pending
    setTabsState((prev) => {
      return {
        ...prev,
        [tabId]: {
          ...prev[tabId],
          isPending: true,
        },
      };
    });
  };

  return (
    <Dialog open={true} onOpenChange={setModalOpen}>
      <DialogTrigger asChild></DialogTrigger>
      <DialogContent className="sm:max-w-[600px] lg:max-w-[700px]">
        <DialogHeader>
          <DialogTitle className="flex items-center">
            <span className="pr-2">{data.type}</span>
            <Badge variant="secondary">ID: {data.id}</Badge>
          </DialogTitle>
          <DialogDescription asChild>
            <div>
              {data.node?.description}
              <div className="flex pt-3">
                <Variable className="edit-node-modal-variable "></Variable>
                <span className="edit-node-modal-span">Parameters</span>
              </div>
            </div>
          </DialogDescription>
        </DialogHeader>

        <div className="edit-node-modal-arrangement">
          <div
            className={classNames(
              "edit-node-modal-box",
              nodeLength > limitScrollFieldsModal
                ? "overflow-scroll overflow-x-hidden custom-scroll"
                : "overflow-hidden"
            )}
          >
            {nodeLength > 0 && (
              <div className="edit-node-modal-table">
                <Table className="table-fixed bg-muted outline-1">
                  <TableHeader className="edit-node-modal-table-header">
                    <TableRow className="">
                      <TableHead className="h-7 text-center">PARAM</TableHead>
                      <TableHead className="h-7 p-0 text-center">
                        VALUE
                      </TableHead>
                      <TableHead className="h-7 text-center">SHOW</TableHead>
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
                        <TableRow key={i} className="h-10">
                          <TableCell className="truncate p-0 text-center text-sm text-foreground sm:px-3">
                            {data.node.template[n].name
                              ? data.node.template[n].name
                              : data.node.template[n].display_name}
                          </TableCell>
                          <TableCell className="w-[300px] p-0 text-center text-xs text-foreground ">
                            {data.node.template[n].type === "str" &&
                            !data.node.template[n].options ? (
                              <div className="mx-auto">
                                {data.node.template[n].list ? (
                                  <InputListComponent
                                    editNode={true}
                                    disabled={disabled}
                                    value={
                                      !data.node.template[n].value ||
                                      data.node.template[n].value === ""
                                        ? [""]
                                        : data.node.template[n].value
                                    }
                                    onChange={(t: string[]) => {
                                      handleOnNewValue(t, n);
                                    }}
                                  />
                                ) : data.node.template[n].multiline ? (
                                  <TextAreaComponent
                                    disabled={disabled}
                                    editNode={true}
                                    value={data.node.template[n].value ?? ""}
                                    onChange={(t: string) => {
                                      handleOnNewValue(t, n);
                                    }}
                                  />
                                ) : (
                                  <InputComponent
                                    editNode={true}
                                    disabled={disabled}
                                    password={
                                      data.node.template[n].password ?? false
                                    }
                                    value={data.node.template[n].value ?? ""}
                                    onChange={(t) => {
                                      handleOnNewValue(t, n);
                                    }}
                                  />
                                )}
                              </div>
                            ) : data.node.template[n].type === "bool" ? (
                              <div className="ml-auto">
                                {" "}
                                <ToggleShadComponent
                                  disabled={disabled}
                                  enabled={data.node.template[n].value}
                                  setEnabled={(t) => {
                                    handleOnNewValue(t, n);
                                  }}
                                  size="small"
                                />
                              </div>
                            ) : data.node.template[n].type === "float" ? (
                              <div className="mx-auto">
                                <FloatComponent
                                  disabled={disabled}
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
                                  onSelect={(t) => handleOnNewValue(t, n)}
                                  value={
                                    data.node.template[n].value ??
                                    "Choose an option"
                                  }
                                ></Dropdown>
                              </div>
                            ) : data.node.template[n].type === "int" ? (
                              <div className="mx-auto">
                                <IntComponent
                                  disabled={disabled}
                                  editNode={true}
                                  value={data.node.template[n].value ?? ""}
                                  onChange={(t) => {
                                    handleOnNewValue(t, n);
                                  }}
                                />
                              </div>
                            ) : data.node.template[n].type === "file" ? (
                              <div className="mx-auto">
                                <InputFileComponent
                                  editNode={true}
                                  disabled={disabled}
                                  value={data.node.template[n].value ?? ""}
                                  onChange={(t: string) => {
                                    handleOnNewValue(t, n);
                                  }}
                                  fileTypes={data.node.template[n].fileTypes}
                                  suffixes={data.node.template[n].suffixes}
                                  onFileChange={(t: string) => {
                                    handleOnNewValue(t, n);
                                  }}
                                ></InputFileComponent>
                              </div>
                            ) : data.node.template[n].type === "prompt" ? (
                              <div className="mx-auto">
                                <PromptAreaComponent
                                  field_name={n}
                                  editNode={true}
                                  disabled={disabled}
                                  nodeClass={data.node}
                                  setNodeClass={(nodeClass) => {
                                    data.node = nodeClass;
                                  }}
                                  value={data.node.template[n].value ?? ""}
                                  onChange={(t: string) => {
                                    handleOnNewValue(t, n);
                                  }}
                                />
                              </div>
                            ) : data.node.template[n].type === "code" ? (
                              <div className="mx-auto">
                                <CodeAreaComponent
                                  disabled={disabled}
                                  editNode={true}
                                  value={data.node.template[n].value ?? ""}
                                  onChange={(t: string) => {
                                    handleOnNewValue(t, n);
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
                                disabled={disabled}
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
