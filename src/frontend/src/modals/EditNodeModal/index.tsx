import { cloneDeep } from "lodash";
import { Variable } from "lucide-react";
import { ReactNode, forwardRef, useContext, useEffect, useState } from "react";
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
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "../../components/ui/table";
import { TabsContext } from "../../contexts/tabsContext";
import { typesContext } from "../../contexts/typesContext";
import { NodeDataType } from "../../types/flow";
import { classNames, limitScrollFieldsModal } from "../../utils";
import BaseModal from "../baseModal";

const EditNodeModal = forwardRef(
  (
    {
      data,
      setData,
      nodeLength,
      children,
    }: {
      data: NodeDataType;
      setData: (data: NodeDataType) => void;
      nodeLength: number;
      children: ReactNode;
    },
    ref
  ) => {
    const [modalOpen, setModalOpen] = useState(false);
    const [myData, setMyData] = useState(data);
    const { setTabsState, tabId } = useContext(TabsContext);
    const { reactFlowInstance } = useContext(typesContext);

    let disabled =
      reactFlowInstance?.getEdges().some((e) => e.targetHandle === data.id) ??
      false;

    function changeAdvanced(n) {
      setMyData((old) => {
        let newData = cloneDeep(old);
        newData.node.template[n].advanced = !newData.node.template[n].advanced;
        return newData;
      });
    }

    const handleOnNewValue = (newValue: any, name) => {
      setMyData((old) => {
        let newData = cloneDeep(old);
        newData.node.template[name].value = newValue;
        return newData;
      });
    };

    useEffect(() => {
      setMyData(data); // reset data to what it is on node when opening modal
    }, [modalOpen]);

    return (
      <BaseModal size="large-h-full" open={modalOpen} setOpen={setModalOpen}>
        <BaseModal.Trigger>{children}</BaseModal.Trigger>
        <BaseModal.Header description={myData.node?.description}>
          <span className="pr-2">{myData.type}</span>
          <Badge variant="secondary">ID: {myData.id}</Badge>
        </BaseModal.Header>
        <BaseModal.Content>
          <div className="flex pb-2">
            <Variable className="edit-node-modal-variable "></Variable>
            <span className="edit-node-modal-span">Parameters</span>
          </div>

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
                      {Object.keys(myData.node.template)
                        .filter(
                          (t) =>
                            t.charAt(0) !== "_" &&
                            myData.node.template[t].show &&
                            (myData.node.template[t].type === "str" ||
                              myData.node.template[t].type === "bool" ||
                              myData.node.template[t].type === "float" ||
                              myData.node.template[t].type === "code" ||
                              myData.node.template[t].type === "prompt" ||
                              myData.node.template[t].type === "file" ||
                              myData.node.template[t].type === "int")
                        )
                        .map((n, i) => (
                          <TableRow key={i} className="h-10">
                            <TableCell className="truncate p-0 text-center text-sm text-foreground sm:px-3">
                              {myData.node.template[n].name
                                ? myData.node.template[n].name
                                : myData.node.template[n].display_name}
                            </TableCell>
                            <TableCell className="w-[300px] p-0 text-center text-xs text-foreground ">
                              {myData.node.template[n].type === "str" &&
                              !myData.node.template[n].options ? (
                                <div className="mx-auto">
                                  {myData.node.template[n].list ? (
                                    <InputListComponent
                                      editNode={true}
                                      disabled={disabled}
                                      value={
                                        !myData.node.template[n].value ||
                                        myData.node.template[n].value === ""
                                          ? [""]
                                          : myData.node.template[n].value
                                      }
                                      onChange={(t: string[]) => {
                                        handleOnNewValue(t, n);
                                      }}
                                    />
                                  ) : myData.node.template[n].multiline ? (
                                    <TextAreaComponent
                                      disabled={disabled}
                                      editNode={true}
                                      value={
                                        myData.node.template[n].value ?? ""
                                      }
                                      onChange={(t: string) => {
                                        handleOnNewValue(t, n);
                                      }}
                                    />
                                  ) : (
                                    <InputComponent
                                      editNode={true}
                                      disabled={disabled}
                                      password={
                                        myData.node.template[n].password ??
                                        false
                                      }
                                      value={
                                        myData.node.template[n].value ?? ""
                                      }
                                      onChange={(t) => {
                                        handleOnNewValue(t, n);
                                      }}
                                    />
                                  )}
                                </div>
                              ) : myData.node.template[n].type === "bool" ? (
                                <div className="ml-auto">
                                  {" "}
                                  <ToggleShadComponent
                                    disabled={disabled}
                                    enabled={myData.node.template[n].value}
                                    setEnabled={(t) => {
                                      handleOnNewValue(t, n);
                                    }}
                                    size="small"
                                  />
                                </div>
                              ) : myData.node.template[n].type === "float" ? (
                                <div className="mx-auto">
                                  <FloatComponent
                                    disabled={disabled}
                                    editNode={true}
                                    value={myData.node.template[n].value ?? ""}
                                    onChange={(t) => {
                                      handleOnNewValue(t, n);
                                    }}
                                  />
                                </div>
                              ) : myData.node.template[n].type === "str" &&
                                myData.node.template[n].options ? (
                                <div className="mx-auto">
                                  <Dropdown
                                    numberOfOptions={nodeLength}
                                    editNode={true}
                                    options={myData.node.template[n].options}
                                    onSelect={(t) => handleOnNewValue(t, n)}
                                    value={
                                      myData.node.template[n].value ??
                                      "Choose an option"
                                    }
                                  ></Dropdown>
                                </div>
                              ) : myData.node.template[n].type === "int" ? (
                                <div className="mx-auto">
                                  <IntComponent
                                    disabled={disabled}
                                    editNode={true}
                                    value={myData.node.template[n].value ?? ""}
                                    onChange={(t) => {
                                      handleOnNewValue(t, n);
                                    }}
                                  />
                                </div>
                              ) : myData.node.template[n].type === "file" ? (
                                <div className="mx-auto">
                                  <InputFileComponent
                                    editNode={true}
                                    disabled={disabled}
                                    value={myData.node.template[n].value ?? ""}
                                    onChange={(t: string) => {
                                      handleOnNewValue(t, n);
                                    }}
                                    fileTypes={
                                      myData.node.template[n].fileTypes
                                    }
                                    suffixes={myData.node.template[n].suffixes}
                                    onFileChange={(t: string) => {
                                      handleOnNewValue(t, n);
                                    }}
                                  ></InputFileComponent>
                                </div>
                              ) : myData.node.template[n].type === "prompt" ? (
                                <div className="mx-auto">
                                  <PromptAreaComponent
                                    field_name={n}
                                    editNode={true}
                                    disabled={disabled}
                                    nodeClass={myData.node}
                                    setNodeClass={(nodeClass) => {
                                      myData.node = nodeClass;
                                    }}
                                    value={myData.node.template[n].value ?? ""}
                                    onChange={(t: string) => {
                                      handleOnNewValue(t, n);
                                    }}
                                  />
                                </div>
                              ) : myData.node.template[n].type === "code" ? (
                                <div className="mx-auto">
                                  <CodeAreaComponent
                                    dynamic={
                                      data.node.template[n].dynamic ?? false
                                    }
                                    setNodeClass={(nodeClass) => {
                                      data.node = nodeClass;
                                    }}
                                    nodeClass={data.node}
                                    disabled={disabled}
                                    editNode={true}
                                    value={myData.node.template[n].value ?? ""}
                                    onChange={(t: string) => {
                                      handleOnNewValue(t, n);
                                    }}
                                  />
                                </div>
                              ) : myData.node.template[n].type === "Any" ? (
                                "-"
                              ) : (
                                <div className="hidden"></div>
                              )}
                            </TableCell>
                            <TableCell className="p-0 text-right">
                              <div className="items-center text-center">
                                <ToggleShadComponent
                                  enabled={!myData.node.template[n].advanced}
                                  setEnabled={(e) => changeAdvanced(n)}
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
        </BaseModal.Content>

        <BaseModal.Footer>
          <Button
            className="mt-3"
            onClick={() => {
              setData(cloneDeep(myData)); //saves data with actual state of modal
              setTabsState((prev) => {
                return {
                  ...prev,
                  [tabId]: {
                    ...prev[tabId],
                    isPending: true,
                  },
                };
              });
              setModalOpen(false);
            }}
            type="submit"
          >
            Save Changes
          </Button>
        </BaseModal.Footer>
      </BaseModal>
    );
  }
);

export default EditNodeModal;
