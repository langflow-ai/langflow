import { useSignal, useSignalEffect } from "@preact/signals-react";
import { cloneDeep } from "lodash";
import { forwardRef, useEffect, useState } from "react";
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
import useFlowStore from "../../stores/flowStore";
import { NodeDataType } from "../../types/flow";
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
    const edges = useFlowStore((state) => state.edges);
    const setNode = useFlowStore((state) => state.setNode);

    const myData = useSignal(data);
    const [render, setRender] = useState(false);
    useSignalEffect(() => {
      setRender(!render);
    });

    function changeAdvanced(n) {
      const newValue = cloneDeep(myData.value);
      newValue.node!.template[n].advanced =
        !newValue.node!.template[n].advanced;
      myData.value = newValue;
    }

    const handleOnNewValue = (newValue: any, name) => {
      const newSignalValue = cloneDeep(myData.value);
      newSignalValue.node!.template[name].value = newValue;
      myData.value = newSignalValue;
    };

    useEffect(() => {
      if (open) {
        myData.value = cloneDeep(data); // clone data to avoid changing data on node when opening modal
      }
    }, [open]);

    const [errorDuplicateKey, setErrorDuplicateKey] = useState(false);

    return (
      <BaseModal
        key={data.id}
        size="large-h-full"
        open={open}
        setOpen={setOpen}
        onChangeOpenModal={(open) => {
          myData.value = cloneDeep(data);
        }}
      >
        <BaseModal.Trigger>
          <></>
        </BaseModal.Trigger>
        <BaseModal.Header description={myData.value.node?.description!}>
          <span className="pr-2">{myData.value.type}</span>
          <Badge variant="secondary">ID: {myData.value.id}</Badge>
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
                      {Object.keys(myData.value.node!.template)
                        .filter(
                          (templateParam) =>
                            templateParam.charAt(0) !== "_" &&
                            myData.value.node?.template[templateParam].show &&
                            LANGFLOW_SUPPORTED_TYPES.has(
                              myData.value?.node?.template[templateParam].type
                            )
                        )
                        .map((templateParam, index) => {
                          let id = {
                            inputTypes:
                              myData.value.node!.template[templateParam]
                                .input_types,
                            type: myData.value.node!.template[templateParam]
                              .type,
                            id: myData.value.id,
                            fieldName: templateParam,
                          };
                          let disabled =
                            edges.some(
                              (edge) =>
                                edge.targetHandle ===
                                scapedJSONStringfy(
                                  myData.value.node!.template[templateParam]
                                    .proxy
                                    ? {
                                        ...id,
                                        proxy:
                                          myData.value.node?.template[
                                            templateParam
                                          ].proxy,
                                      }
                                    : id
                                )
                            ) ?? false;
                          return (
                            <TableRow key={index} className="h-10">
                              <TableCell className="truncate p-0 text-center text-sm text-foreground sm:px-3">
                                <ShadTooltip
                                  content={
                                    myData.value.node?.template[templateParam]
                                      .proxy
                                      ? myData.value.node?.template[
                                          templateParam
                                        ].proxy?.id
                                      : null
                                  }
                                >
                                  <span>
                                    {myData.value.node?.template[templateParam]
                                      .display_name
                                      ? myData.value?.node?.template[
                                          templateParam
                                        ].display_name
                                      : myData.value.node?.template[
                                          templateParam
                                        ].name}
                                  </span>
                                </ShadTooltip>
                              </TableCell>
                              <TableCell className="w-[300px] p-0 text-center text-xs text-foreground ">
                                {myData.value.node?.template[templateParam]
                                  .type === "str" &&
                                !myData.value?.node?.template[templateParam]
                                  .options ? (
                                  <div className="mx-auto">
                                    {myData.value?.node?.template[templateParam]
                                      .list ? (
                                      <InputListComponent
                                        editNode={true}
                                        disabled={disabled}
                                        value={
                                          !myData.value?.node?.template[
                                            templateParam
                                          ].value ||
                                          myData.value?.node?.template[
                                            templateParam
                                          ].value === ""
                                            ? [""]
                                            : myData.value?.node?.template[
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
                                    ) : myData.value?.node?.template[
                                        templateParam
                                      ].multiline ? (
                                      <TextAreaComponent
                                        id={"textarea-edit-" + index}
                                        data-testid={"textarea-edit-" + index}
                                        disabled={disabled}
                                        editNode={true}
                                        value={
                                          myData.value?.node?.template[
                                            templateParam
                                          ].value ?? ""
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
                                          myData.value?.node?.template[
                                            templateParam
                                          ].password ?? false
                                        }
                                        value={
                                          myData.value?.node?.template[
                                            templateParam
                                          ].value ?? ""
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
                                ) : myData.value.node?.template[templateParam]
                                    .type === "NestedDict" ? (
                                  <div className="  w-full">
                                    <DictComponent
                                      disabled={disabled}
                                      editNode={true}
                                      value={
                                        myData.value.node!.template[
                                          templateParam
                                        ]?.value?.toString() === "{}"
                                          ? {
                                              yourkey: "value",
                                            }
                                          : myData.value.node!.template[
                                              templateParam
                                            ].value
                                      }
                                      onChange={(newValue) => {
                                        myData.value.node!.template[
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
                                ) : myData.value.node?.template[templateParam]
                                    .type === "dict" ? (
                                  <div
                                    className={classNames(
                                      "max-h-48 w-full overflow-auto custom-scroll",
                                      myData.value.node!.template[templateParam]
                                        .value?.length > 1
                                        ? "my-3"
                                        : ""
                                    )}
                                  >
                                    <KeypairListComponent
                                      disabled={disabled}
                                      editNode={true}
                                      value={
                                        myData.value.node!.template[
                                          templateParam
                                        ].value?.length === 0 ||
                                        !myData.value.node!.template[
                                          templateParam
                                        ].value
                                          ? [{ "": "" }]
                                          : convertObjToArray(
                                              myData.value.node!.template[
                                                templateParam
                                              ].value
                                            )
                                      }
                                      duplicateKey={errorDuplicateKey}
                                      onChange={(newValue) => {
                                        const valueToNumbers =
                                          convertValuesToNumbers(newValue);
                                        myData.value.node!.template[
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
                                ) : myData.value.node?.template[templateParam]
                                    .type === "bool" ? (
                                  <div className="ml-auto">
                                    {" "}
                                    <ToggleShadComponent
                                      id={"toggle-edit-" + index}
                                      disabled={disabled}
                                      enabled={
                                        myData.value?.node?.template[
                                          templateParam
                                        ].value
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
                                ) : myData.value.node?.template[templateParam]
                                    .type === "float" ? (
                                  <div className="mx-auto">
                                    <FloatComponent
                                      disabled={disabled}
                                      editNode={true}
                                      rangeSpec={
                                        myData.value.node!.template[
                                          templateParam
                                        ].rangeSpec
                                      }
                                      value={
                                        myData.value?.node?.template[
                                          templateParam
                                        ].value ?? ""
                                      }
                                      onChange={(value) => {
                                        handleOnNewValue(value, templateParam);
                                      }}
                                    />
                                  </div>
                                ) : myData.value.node?.template[templateParam]
                                    .type === "str" &&
                                  myData.value?.node?.template[templateParam]
                                    .options ? (
                                  <div className="mx-auto">
                                    <Dropdown
                                      numberOfOptions={nodeLength}
                                      editNode={true}
                                      options={
                                        myData.value?.node?.template[
                                          templateParam
                                        ].options
                                      }
                                      onSelect={(value) =>
                                        handleOnNewValue(value, templateParam)
                                      }
                                      value={
                                        myData.value?.node?.template[
                                          templateParam
                                        ].value ?? "Choose an option"
                                      }
                                      id={"dropdown-edit-" + index}
                                    ></Dropdown>
                                  </div>
                                ) : myData.value.node?.template[templateParam]
                                    .type === "int" ? (
                                  <div className="mx-auto">
                                    <IntComponent
                                      id={"edit-int-input-" + index}
                                      disabled={disabled}
                                      editNode={true}
                                      value={
                                        myData.value?.node?.template[
                                          templateParam
                                        ].value ?? ""
                                      }
                                      onChange={(value) => {
                                        handleOnNewValue(value, templateParam);
                                      }}
                                    />
                                  </div>
                                ) : myData.value.node?.template[templateParam]
                                    .type === "file" ? (
                                  <div className="mx-auto">
                                    <InputFileComponent
                                      editNode={true}
                                      disabled={disabled}
                                      value={
                                        myData.value?.node?.template[
                                          templateParam
                                        ].value ?? ""
                                      }
                                      onChange={(value: string | string[]) => {
                                        handleOnNewValue(value, templateParam);
                                      }}
                                      fileTypes={
                                        myData.value?.node?.template[
                                          templateParam
                                        ].fileTypes
                                      }
                                      onFileChange={(filePath: string) => {
                                        data.node!.template[
                                          templateParam
                                        ].file_path = filePath;
                                      }}
                                    ></InputFileComponent>
                                  </div>
                                ) : myData.value.node?.template[templateParam]
                                    .type === "prompt" ? (
                                  <div className="mx-auto">
                                    <PromptAreaComponent
                                      readonly={
                                        myData.value.node?.flow ? true : false
                                      }
                                      field_name={templateParam}
                                      editNode={true}
                                      disabled={disabled}
                                      nodeClass={myData.value.node}
                                      setNodeClass={(nodeClass) => {
                                        myData.value.node = nodeClass;
                                      }}
                                      value={
                                        myData.value?.node?.template[
                                          templateParam
                                        ].value ?? ""
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
                                ) : myData.value.node?.template[templateParam]
                                    .type === "code" ? (
                                  <div className="mx-auto">
                                    <CodeAreaComponent
                                      readonly={
                                        myData.value.node?.flow &&
                                        myData.value?.node?.template[
                                          templateParam
                                        ].dynamic
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
                                        myData.value?.node?.template[
                                          templateParam
                                        ].value ?? ""
                                      }
                                      onChange={(value: string | string[]) => {
                                        handleOnNewValue(value, templateParam);
                                      }}
                                      id={"code-area-edit" + index}
                                    />
                                  </div>
                                ) : myData.value.node?.template[templateParam]
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
                                      myData.value.node?.template[templateParam]
                                        .name
                                    }
                                    enabled={
                                      !myData.value.node?.template[
                                        templateParam
                                      ].advanced
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
              setNode(data.id, (old) => ({
                ...old,
                data: {
                  ...old.data,
                  node: myData.value.node,
                },
              }));
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
