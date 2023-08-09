import { cloneDeep } from "lodash";
import { ReactNode, forwardRef, useContext, useEffect, useState } from "react";
import CodeAreaComponent from "../../components/codeAreaComponent";
import Dropdown from "../../components/dropdownComponent";
import FloatComponent from "../../components/floatComponent";
import IconComponent from "../../components/genericIconComponent";
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
import { limitScrollFieldsModal } from "../../constants/constants";
import { TabsContext } from "../../contexts/tabsContext";
import { typesContext } from "../../contexts/typesContext";
import { NodeDataType } from "../../types/flow";
import { classNames } from "../../utils/utils";
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
      reactFlowInstance
        ?.getEdges()
        .some((edge) => edge.targetHandle === data.id) ?? false;

    function changeAdvanced(templateParam) {
      setMyData((old) => {
        let newData = cloneDeep(old);
        newData.node.template[templateParam].advanced =
          !newData.node.template[templateParam].advanced;
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
            <IconComponent
              name="Variable"
              className="edit-node-modal-variable "
            />
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
                          (templateParam) =>
                            templateParam.charAt(0) !== "_" &&
                            myData.node.template[templateParam].show &&
                            (myData.node.template[templateParam].type ===
                              "str" ||
                              myData.node.template[templateParam].type ===
                                "bool" ||
                              myData.node.template[templateParam].type ===
                                "float" ||
                              myData.node.template[templateParam].type ===
                                "code" ||
                              myData.node.template[templateParam].type ===
                                "prompt" ||
                              myData.node.template[templateParam].type ===
                                "file" ||
                              myData.node.template[templateParam].type ===
                                "int")
                        )
                        .map((templateParam, index) => (
                          <TableRow key={index} className="h-10">
                            <TableCell className="truncate p-0 text-center text-sm text-foreground sm:px-3">
                              {myData.node.template[templateParam].name
                                ? myData.node.template[templateParam].name
                                : myData.node.template[templateParam]
                                    .display_name}
                            </TableCell>
                            <TableCell className="w-[300px] p-0 text-center text-xs text-foreground ">
                              {myData.node.template[templateParam].type ===
                                "str" &&
                              !myData.node.template[templateParam].options ? (
                                <div className="mx-auto">
                                  {myData.node.template[templateParam].list ? (
                                    <InputListComponent
                                      editNode={true}
                                      disabled={disabled}
                                      value={
                                        !myData.node.template[templateParam]
                                          .value ||
                                        myData.node.template[templateParam]
                                          .value === ""
                                          ? [""]
                                          : myData.node.template[templateParam]
                                              .value
                                      }
                                      onChange={(value: string[]) => {
                                        handleOnNewValue(value, templateParam);
                                      }}
                                    />
                                  ) : myData.node.template[templateParam]
                                      .multiline ? (
                                    <TextAreaComponent
                                      disabled={disabled}
                                      editNode={true}
                                      value={
                                        myData.node.template[templateParam]
                                          .value ?? ""
                                      }
                                      onChange={(value: string) => {
                                        handleOnNewValue(value, templateParam);
                                      }}
                                    />
                                  ) : (
                                    <InputComponent
                                      editNode={true}
                                      disabled={disabled}
                                      password={
                                        myData.node.template[templateParam]
                                          .password ?? false
                                      }
                                      value={
                                        myData.node.template[templateParam]
                                          .value ?? ""
                                      }
                                      onChange={(value) => {
                                        handleOnNewValue(value, templateParam);
                                      }}
                                    />
                                  )}
                                </div>
                              ) : myData.node.template[templateParam].type ===
                                "bool" ? (
                                <div className="ml-auto">
                                  {" "}
                                  <ToggleShadComponent
                                    disabled={disabled}
                                    enabled={
                                      myData.node.template[templateParam].value
                                    }
                                    setEnabled={(isEnabled) => {
                                      handleOnNewValue(
                                        isEnabled,
                                        templateParam
                                      );
                                    }}
                                    size="small"
                                  />
                                </div>
                              ) : myData.node.template[templateParam].type ===
                                "float" ? (
                                <div className="mx-auto">
                                  <FloatComponent
                                    disabled={disabled}
                                    editNode={true}
                                    value={
                                      myData.node.template[templateParam]
                                        .value ?? ""
                                    }
                                    onChange={(value) => {
                                      handleOnNewValue(value, templateParam);
                                    }}
                                  />
                                </div>
                              ) : myData.node.template[templateParam].type ===
                                  "str" &&
                                myData.node.template[templateParam].options ? (
                                <div className="mx-auto">
                                  <Dropdown
                                    numberOfOptions={nodeLength}
                                    editNode={true}
                                    options={
                                      myData.node.template[templateParam]
                                        .options
                                    }
                                    onSelect={(value) =>
                                      handleOnNewValue(value, templateParam)
                                    }
                                    value={
                                      myData.node.template[templateParam]
                                        .value ?? "Choose an option"
                                    }
                                  ></Dropdown>
                                </div>
                              ) : myData.node.template[templateParam].type ===
                                "int" ? (
                                <div className="mx-auto">
                                  <IntComponent
                                    disabled={disabled}
                                    editNode={true}
                                    value={
                                      myData.node.template[templateParam]
                                        .value ?? ""
                                    }
                                    onChange={(value) => {
                                      handleOnNewValue(value, templateParam);
                                    }}
                                  />
                                </div>
                              ) : myData.node.template[templateParam].type ===
                                "file" ? (
                                <div className="mx-auto">
                                  <InputFileComponent
                                    editNode={true}
                                    disabled={disabled}
                                    value={
                                      myData.node.template[templateParam]
                                        .value ?? ""
                                    }
                                    onChange={(value: string) => {
                                      handleOnNewValue(value, templateParam);
                                    }}
                                    fileTypes={
                                      myData.node.template[templateParam]
                                        .fileTypes
                                    }
                                    suffixes={
                                      myData.node.template[templateParam]
                                        .suffixes
                                    }
                                    onFileChange={(filePath: string) => {
                                      data.node.template[
                                        templateParam
                                      ].file_path = filePath;
                                    }}
                                  ></InputFileComponent>
                                </div>
                              ) : myData.node.template[templateParam].type ===
                                "prompt" ? (
                                <div className="mx-auto">
                                  <PromptAreaComponent
                                    field_name={templateParam}
                                    editNode={true}
                                    disabled={disabled}
                                    nodeClass={myData.node}
                                    setNodeClass={(nodeClass) => {
                                      myData.node = nodeClass;
                                    }}
                                    value={
                                      myData.node.template[templateParam]
                                        .value ?? ""
                                    }
                                    onChange={(value: string) => {
                                      handleOnNewValue(value, templateParam);
                                    }}
                                  />
                                </div>
                              ) : myData.node.template[templateParam].type ===
                                "code" ? (
                                <div className="mx-auto">
                                  <CodeAreaComponent
                                    dynamic={
                                      data.node.template[templateParam]
                                        .dynamic ?? false
                                    }
                                    setNodeClass={(nodeClass) => {
                                      data.node = nodeClass;
                                    }}
                                    nodeClass={data.node}
                                    disabled={disabled}
                                    editNode={true}
                                    value={
                                      myData.node.template[templateParam]
                                        .value ?? ""
                                    }
                                    onChange={(value: string) => {
                                      handleOnNewValue(value, templateParam);
                                    }}
                                  />
                                </div>
                              ) : myData.node.template[templateParam].type ===
                                "Any" ? (
                                "-"
                              ) : (
                                <div className="hidden"></div>
                              )}
                            </TableCell>
                            <TableCell className="p-0 text-right">
                              <div className="items-center text-center">
                                <ToggleShadComponent
                                  enabled={
                                    !myData.node.template[templateParam]
                                      .advanced
                                  }
                                  setEnabled={(e) =>
                                    changeAdvanced(templateParam)
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
