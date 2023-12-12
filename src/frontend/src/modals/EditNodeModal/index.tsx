import { cloneDeep } from "lodash";
import { forwardRef, useContext, useEffect, useState } from "react";
import { useUpdateNodeInternals } from "reactflow";
import ShadTooltip from "../../components/ShadTooltipComponent";
import CodeAreaComponent from "../../components/codeAreaComponent";
import DictComponent from "../../components/dictComponent";
import Dropdown from "../../components/dropdownComponent";
import FloatComponent from "../../components/floatComponent";
import IconComponent from "../../components/genericIconComponent";
import InputComponent from "../../components/inputComponent";
import InputFileComponent from "../../components/inputFileComponent";
import InputListComponent from "../../components/inputListComponent";
import IntComponent from "../../components/intComponent";
import KeypairListComponent from "../../components/keypairListComponent";
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
import {
  LANGFLOW_SUPPORTED_TYPES,
  limitScrollFieldsModal,
} from "../../constants/constants";
import { alertContext } from "../../contexts/alertContext";
import { FlowsContext } from "../../contexts/flowsContext";
import { typesContext } from "../../contexts/typesContext";
import { NodeDataType } from "../../types/flow";
import { FlowsState } from "../../types/tabs";
import {
  convertObjToArray,
  convertValuesToNumbers,
  hasDuplicateKeys,
  scapedJSONStringfy,
} from "../../utils/reactflowUtils";
import { classNames } from "../../utils/utils";
import BaseModal from "../baseModal";

const EditNodeModal = forwardRef(
  (
    {
      data,
      nodeLength,
      open,
      setOpen,
    }: {
      data: NodeDataType;
      nodeLength: number;
      open: boolean;
      setOpen: (open: boolean) => void;
    },
    ref
  ) => {
    const updateNodeInternals = useUpdateNodeInternals();

    const [myData, setMyData] = useState(data);

    const { setTabsState, tabId } = useContext(FlowsContext);
    const { reactFlowInstance } = useContext(typesContext);
    const { setModalContextOpen } = useContext(alertContext);

    function changeAdvanced(n) {
      setMyData((old) => {
        let newData = cloneDeep(old);
        newData.node!.template[n].advanced =
          !newData.node!.template[n].advanced;
        return newData;
      });
    }

    const handleOnNewValue = (newValue: any, name) => {
      setMyData((old) => {
        let newData = cloneDeep(old);
        newData.node!.template[name].value = newValue;
        return newData;
      });
      updateNodeInternals(data.id);
    };

    useEffect(() => {
      if (open) {
        setMyData(data); // reset data to what it is on node when opening modal
      }
      setModalContextOpen(open);
    }, [open]);

    const [errorDuplicateKey, setErrorDuplicateKey] = useState(false);

    return (
      <BaseModal
        key={data.id}
        size="large-h-full"
        open={open}
        setOpen={setOpen}
        onChangeOpenModal={(open) => {
          setMyData(data);
        }}
      >
        <BaseModal.Trigger>
          <></>
        </BaseModal.Trigger>
        <BaseModal.Header description={myData.node?.description!}>
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
                  : ""
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
                      {Object.keys(myData.node!.template)
                        .filter(
                          (templateParam) =>
                            templateParam.charAt(0) !== "_" &&
                            myData.node?.template[templateParam].show &&
                            LANGFLOW_SUPPORTED_TYPES.has(
                              myData.node.template[templateParam].type
                            )
                        )
                        .map((templateParam, index) => {
                          let id = {
                            inputTypes:
                              myData.node!.template[templateParam].input_types,
                            type: myData.node!.template[templateParam].type,
                            id: myData.id,
                            fieldName: templateParam,
                          };
                          let disabled =
                            reactFlowInstance?.getEdges().some(
                              (edge) =>
                                edge.targetHandle ===
                                scapedJSONStringfy(
                                  myData.node!.template[templateParam].proxy
                                    ? {
                                        ...id,
                                        proxy:
                                          myData.node?.template[templateParam]
                                            .proxy,
                                      }
                                    : id
                                )
                            ) ?? false;
                          return (
                            <TableRow key={index} className="h-10">
                              <TableCell className="truncate p-0 text-center text-sm text-foreground sm:px-3">
                                <ShadTooltip
                                  content={
                                    myData.node?.template[templateParam].proxy
                                      ? myData.node?.template[templateParam]
                                          .proxy?.id
                                      : null
                                  }
                                >
                                  <span>
                                    {myData.node?.template[templateParam]
                                      .display_name
                                      ? myData.node.template[templateParam]
                                          .display_name
                                      : myData.node?.template[templateParam]
                                          .name}
                                  </span>
                                </ShadTooltip>
                              </TableCell>
                              <TableCell className="w-[300px] p-0 text-center text-xs text-foreground ">
                                {myData.node?.template[templateParam].type ===
                                  "str" &&
                                !myData.node.template[templateParam].options ? (
                                  <div className="mx-auto">
                                    {myData.node.template[templateParam]
                                      .list ? (
                                      <InputListComponent
                                        editNode={true}
                                        disabled={disabled}
                                        value={
                                          !myData.node.template[templateParam]
                                            .value ||
                                          myData.node.template[templateParam]
                                            .value === ""
                                            ? [""]
                                            : myData.node.template[
                                                templateParam
                                              ].value
                                        }
                                        onChange={(value: string[]) => {
                                          handleOnNewValue(
                                            value,
                                            templateParam
                                          );
                                        }}
                                      />
                                    ) : myData.node.template[templateParam]
                                        .multiline ? (
                                      <TextAreaComponent
                                        id={"textarea-edit-" + index}
                                        data-testid={"textarea-edit-" + index}
                                        disabled={disabled}
                                        editNode={true}
                                        value={
                                          myData.node.template[templateParam]
                                            .value ?? ""
                                        }
                                        onChange={(
                                          value: string | string[]
                                        ) => {
                                          handleOnNewValue(
                                            value,
                                            templateParam
                                          );
                                        }}
                                      />
                                    ) : (
                                      <InputComponent
                                        id={"input-" + index}
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
                                          handleOnNewValue(
                                            value,
                                            templateParam
                                          );
                                        }}
                                      />
                                    )}
                                  </div>
                                ) : myData.node?.template[templateParam]
                                    .type === "NestedDict" ? (
                                  <div className="  w-full">
                                    <DictComponent
                                      disabled={disabled}
                                      editNode={true}
                                      value={
                                        myData.node!.template[
                                          templateParam
                                        ]?.value?.toString() === "{}"
                                          ? {
                                              yourkey: "value",
                                            }
                                          : myData.node!.template[templateParam]
                                              .value
                                      }
                                      onChange={(newValue) => {
                                        myData.node!.template[
                                          templateParam
                                        ].value = newValue;
                                        handleOnNewValue(
                                          newValue,
                                          templateParam
                                        );
                                      }}
                                      id="editnode-div-dict-input"
                                    />
                                  </div>
                                ) : myData.node?.template[templateParam]
                                    .type === "dict" ? (
                                  <div
                                    className={classNames(
                                      "max-h-48 w-full overflow-auto custom-scroll",
                                      myData.node!.template[templateParam].value
                                        ?.length > 1
                                        ? "my-3"
                                        : ""
                                    )}
                                  >
                                    <KeypairListComponent
                                      disabled={disabled}
                                      editNode={true}
                                      value={
                                        myData.node!.template[templateParam]
                                          .value?.length === 0 ||
                                        !myData.node!.template[templateParam]
                                          .value
                                          ? [{ "": "" }]
                                          : convertObjToArray(
                                              myData.node!.template[
                                                templateParam
                                              ].value
                                            )
                                      }
                                      duplicateKey={errorDuplicateKey}
                                      onChange={(newValue) => {
                                        const valueToNumbers =
                                          convertValuesToNumbers(newValue);
                                        myData.node!.template[
                                          templateParam
                                        ].value = valueToNumbers;
                                        setErrorDuplicateKey(
                                          hasDuplicateKeys(valueToNumbers)
                                        );
                                        handleOnNewValue(
                                          valueToNumbers,
                                          templateParam
                                        );
                                      }}
                                    />
                                  </div>
                                ) : myData.node?.template[templateParam]
                                    .type === "bool" ? (
                                  <div className="ml-auto">
                                    {" "}
                                    <ToggleShadComponent
                                      id={"toggle-edit-" + index}
                                      disabled={disabled}
                                      enabled={
                                        myData.node.template[templateParam]
                                          .value
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
                                ) : myData.node?.template[templateParam]
                                    .type === "float" ? (
                                  <div className="mx-auto">
                                    <FloatComponent
                                      disabled={disabled}
                                      editNode={true}
                                      rangeSpec={
                                        myData.node!.template[templateParam]
                                          .rangeSpec
                                      }
                                      value={
                                        myData.node.template[templateParam]
                                          .value ?? ""
                                      }
                                      onChange={(value) => {
                                        handleOnNewValue(value, templateParam);
                                      }}
                                    />
                                  </div>
                                ) : myData.node?.template[templateParam]
                                    .type === "str" &&
                                  myData.node.template[templateParam]
                                    .options ? (
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
                                      id={"dropdown-edit-" + index}
                                    ></Dropdown>
                                  </div>
                                ) : myData.node?.template[templateParam]
                                    .type === "int" ? (
                                  <div className="mx-auto">
                                    <IntComponent
                                      id={"edit-int-input-" + index}
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
                                ) : myData.node?.template[templateParam]
                                    .type === "file" ? (
                                  <div className="mx-auto">
                                    <InputFileComponent
                                      editNode={true}
                                      disabled={disabled}
                                      value={
                                        myData.node.template[templateParam]
                                          .value ?? ""
                                      }
                                      onChange={(value: string | string[]) => {
                                        handleOnNewValue(value, templateParam);
                                      }}
                                      fileTypes={
                                        myData.node.template[templateParam]
                                          .fileTypes
                                      }
                                      onFileChange={(filePath: string) => {
                                        data.node!.template[
                                          templateParam
                                        ].file_path = filePath;
                                      }}
                                    ></InputFileComponent>
                                  </div>
                                ) : myData.node?.template[templateParam]
                                    .type === "prompt" ? (
                                  <div className="mx-auto">
                                    <PromptAreaComponent
                                      readonly={
                                        myData.node?.flow ? true : false
                                      }
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
                                      onChange={(value: string | string[]) => {
                                        handleOnNewValue(value, templateParam);
                                      }}
                                      id={"prompt-area-edit" + index}
                                      data-testid={
                                        "modal-prompt-input-" + index
                                      }
                                    />
                                  </div>
                                ) : myData.node?.template[templateParam]
                                    .type === "code" ? (
                                  <div className="mx-auto">
                                    <CodeAreaComponent
                                      readonly={
                                        myData.node?.flow &&
                                        myData.node.template[templateParam]
                                          .dynamic
                                          ? true
                                          : false
                                      }
                                      dynamic={
                                        data.node!.template[templateParam]
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
                                      onChange={(value: string | string[]) => {
                                        handleOnNewValue(value, templateParam);
                                      }}
                                      id={"code-area-edit" + index}
                                    />
                                  </div>
                                ) : myData.node?.template[templateParam]
                                    .type === "Any" ? (
                                  "-"
                                ) : (
                                  <div className="hidden"></div>
                                )}
                              </TableCell>
                              <TableCell className="p-0 text-right">
                                <div className="items-center text-center">
                                  <ToggleShadComponent
                                    id={
                                      "show" +
                                      myData.node?.template[templateParam].name
                                    }
                                    enabled={
                                      !myData.node?.template[templateParam]
                                        .advanced
                                    }
                                    setEnabled={(e) => {
                                      changeAdvanced(templateParam);
                                    }}
                                    disabled={disabled}
                                    size="small"
                                  />
                                </div>
                              </TableCell>
                            </TableRow>
                          );
                        })}
                    </TableBody>
                  </Table>
                </div>
              )}
            </div>
          </div>
        </BaseModal.Content>

        <BaseModal.Footer>
          <Button
            id={"saveChangesBtn"}
            className="mt-3"
            onClick={() => {
              data.node = myData.node;
              //@ts-ignore
              setTabsState((prev: FlowsState) => {
                return {
                  ...prev,
                  [tabId]: {
                    ...prev[tabId],
                    isPending: true,
                  },
                };
              });
              setOpen(false);
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
