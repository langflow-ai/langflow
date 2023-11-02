import { cloneDeep } from "lodash";
import {
  ReactNode,
  forwardRef,
  useContext,
  useEffect,
  useRef,
  useState,
} from "react";
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
import { limitScrollFieldsModal } from "../../constants/constants";
import { FlowsContext } from "../../contexts/flowsContext";
import { typesContext } from "../../contexts/typesContext";
import { NodeDataType } from "../../types/flow";
import { FlowsState } from "../../types/tabs";
import {
  convertObjToArray,
  convertValuesToNumbers,
  hasDuplicateKeys,
} from "../../utils/reactflowUtils";
import { classNames } from "../../utils/utils";
import BaseModal from "../baseModal";

const EditNodeModal = forwardRef(
  (
    {
      data,
      setData,
      nodeLength,
      children,
      open,
      onClose,
    }: {
      data: NodeDataType;
      setData: (data: NodeDataType) => void;
      nodeLength: number;
      children: ReactNode;
      open?: boolean;
      onClose?: (close: boolean) => void;
    },
    ref
  ) => {
    const [modalOpen, setModalOpen] = useState(open ?? false);
    const updateNodeInternals = useUpdateNodeInternals();

    const myData = useRef(data);

    const { setTabsState, tabId } = useContext(FlowsContext);
    const { reactFlowInstance } = useContext(typesContext);
    let disabled =
      reactFlowInstance
        ?.getEdges()
        .some((edge) => edge.targetHandle === data.id) ?? false;

    function changeAdvanced(n) {
      myData.current.node!.template[n].advanced =
        !myData.current.node!.template[n].advanced;
      setAdv(!adv);
    }

    const handleOnNewValue = (newValue: any, name) => {
      myData.current.node!.template[name].value = newValue;
      setDataValue(newValue);
      updateNodeInternals(data.id);
    };

    useEffect(() => {
      if (modalOpen) {
        myData.current = data; // reset data to what it is on node when opening modal
        onClose!(modalOpen);
      }
    }, [modalOpen]);

    const [errorDuplicateKey, setErrorDuplicateKey] = useState(false);
    const [adv, setAdv] = useState<boolean | null>(null);
    const [dataValue, setDataValue] = useState(data);

    return (
      <BaseModal
        key={data.id}
        size="large-h-full"
        open={modalOpen}
        setOpen={setModalOpen}
        onChangeOpenModal={(open) => {
          myData.current = data;
        }}
      >
        <BaseModal.Trigger>{children}</BaseModal.Trigger>
        <BaseModal.Header description={myData.current.node?.description!}>
          <span className="pr-2">{myData.current.type}</span>
          <Badge variant="secondary">ID: {myData.current.id}</Badge>
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
                      {Object.keys(myData.current.node!.template)
                        .filter(
                          (templateParam) =>
                            templateParam.charAt(0) !== "_" &&
                            myData.current.node?.template[templateParam].show &&
                            (myData.current.node.template[templateParam]
                              .type === "str" ||
                              myData.current.node.template[templateParam]
                                .type === "bool" ||
                              myData.current.node.template[templateParam]
                                .type === "float" ||
                              myData.current.node.template[templateParam]
                                .type === "code" ||
                              myData.current.node.template[templateParam]
                                .type === "prompt" ||
                              myData.current.node.template[templateParam]
                                .type === "file" ||
                              myData.current.node.template[templateParam]
                                .type === "int" ||
                              myData.current.node.template[templateParam]
                                .type === "dict" ||
                              myData.current.node.template[templateParam]
                                .type === "NestedDict")
                        )
                        .map((templateParam, index) => (
                          <TableRow key={index} className="h-10">
                            <TableCell className="truncate p-0 text-center text-sm text-foreground sm:px-3">
                              <ShadTooltip
                                content={
                                  myData.current.node?.template[templateParam]
                                    .proxy
                                    ? myData.current.node?.template[
                                        templateParam
                                      ].proxy?.id
                                    : null
                                }
                              >
                                <span>
                                  {myData.current.node?.template[templateParam]
                                    .display_name
                                    ? myData.current.node.template[
                                        templateParam
                                      ].display_name
                                    : myData.current.node?.template[
                                        templateParam
                                      ].name}
                                </span>
                              </ShadTooltip>
                            </TableCell>
                            <TableCell className="w-[300px] p-0 text-center text-xs text-foreground ">
                              {myData.current.node?.template[templateParam]
                                .type === "str" &&
                              !myData.current.node.template[templateParam]
                                .options ? (
                                <div className="mx-auto">
                                  {myData.current.node.template[templateParam]
                                    .list ? (
                                    <InputListComponent
                                      editNode={true}
                                      disabled={disabled}
                                      value={
                                        !myData.current.node.template[
                                          templateParam
                                        ].value ||
                                        myData.current.node.template[
                                          templateParam
                                        ].value === ""
                                          ? [""]
                                          : myData.current.node.template[
                                              templateParam
                                            ].value
                                      }
                                      onChange={(value: string[]) => {
                                        handleOnNewValue(value, templateParam);
                                      }}
                                    />
                                  ) : myData.current.node.template[
                                      templateParam
                                    ].multiline ? (
                                    <TextAreaComponent
                                      id={"textarea-edit-" + index}
                                      disabled={disabled}
                                      editNode={true}
                                      value={
                                        myData.current.node.template[
                                          templateParam
                                        ].value ?? ""
                                      }
                                      onChange={(value: string | string[]) => {
                                        handleOnNewValue(value, templateParam);
                                      }}
                                    />
                                  ) : (
                                    <InputComponent
                                      id={"input-" + index}
                                      editNode={true}
                                      disabled={disabled}
                                      password={
                                        myData.current.node.template[
                                          templateParam
                                        ].password ?? false
                                      }
                                      value={
                                        myData.current.node.template[
                                          templateParam
                                        ].value ?? ""
                                      }
                                      onChange={(value) => {
                                        handleOnNewValue(value, templateParam);
                                      }}
                                    />
                                  )}
                                </div>
                              ) : myData.current.node?.template[templateParam]
                                  .type === "NestedDict" ? (
                                <div className="  w-full">
                                  <DictComponent
                                    disabled={disabled}
                                    editNode={true}
                                    value={
                                      myData.current.node!.template[
                                        templateParam
                                      ].value.toString() === "{}"
                                        ? {
                                            yourkey: "value",
                                          }
                                        : myData.current.node!.template[
                                            templateParam
                                          ].value
                                    }
                                    onChange={(newValue) => {
                                      myData.current.node!.template[
                                        templateParam
                                      ].value = newValue;
                                      handleOnNewValue(newValue, templateParam);
                                    }}
                                  />
                                </div>
                              ) : myData.current.node?.template[templateParam]
                                  .type === "dict" ? (
                                <div
                                  className={classNames(
                                    "max-h-48 w-full overflow-auto custom-scroll",
                                    myData.current.node!.template[templateParam]
                                      .value?.length > 1
                                      ? "my-3"
                                      : ""
                                  )}
                                >
                                  <KeypairListComponent
                                    dataValue={dataValue}
                                    advanced={adv}
                                    disabled={disabled}
                                    editNode={true}
                                    value={
                                      myData.current.node!.template[
                                        templateParam
                                      ].value?.length === 0 ||
                                      !myData.current.node!.template[
                                        templateParam
                                      ].value
                                        ? [{ "": "" }]
                                        : convertObjToArray(
                                            myData.current.node!.template[
                                              templateParam
                                            ].value
                                          )
                                    }
                                    duplicateKey={errorDuplicateKey}
                                    onChange={(newValue) => {
                                      const valueToNumbers =
                                        convertValuesToNumbers(newValue);
                                      myData.current.node!.template[
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
                              ) : myData.current.node?.template[templateParam]
                                  .type === "bool" ? (
                                <div className="ml-auto">
                                  {" "}
                                  <ToggleShadComponent
                                    id={"toggle-edit-" + index}
                                    disabled={disabled}
                                    enabled={
                                      myData.current.node.template[
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
                              ) : myData.current.node?.template[templateParam]
                                  .type === "float" ? (
                                <div className="mx-auto">
                                  <FloatComponent
                                    disabled={disabled}
                                    editNode={true}
                                    value={
                                      myData.current.node.template[
                                        templateParam
                                      ].value ?? ""
                                    }
                                    onChange={(value) => {
                                      handleOnNewValue(value, templateParam);
                                    }}
                                  />
                                </div>
                              ) : myData.current.node?.template[templateParam]
                                  .type === "str" &&
                                myData.current.node.template[templateParam]
                                  .options ? (
                                <div className="mx-auto">
                                  <Dropdown
                                    numberOfOptions={nodeLength}
                                    editNode={true}
                                    options={
                                      myData.current.node.template[
                                        templateParam
                                      ].options
                                    }
                                    onSelect={(value) =>
                                      handleOnNewValue(value, templateParam)
                                    }
                                    value={
                                      myData.current.node.template[
                                        templateParam
                                      ].value ?? "Choose an option"
                                    }
                                  ></Dropdown>
                                </div>
                              ) : myData.current.node?.template[templateParam]
                                  .type === "int" ? (
                                <div className="mx-auto">
                                  <IntComponent
                                    id={"int-input-" + index}
                                    disabled={disabled}
                                    editNode={true}
                                    value={
                                      myData.current.node.template[
                                        templateParam
                                      ].value ?? ""
                                    }
                                    onChange={(value) => {
                                      handleOnNewValue(value, templateParam);
                                    }}
                                  />
                                </div>
                              ) : myData.current.node?.template[templateParam]
                                  .type === "file" ? (
                                <div className="mx-auto">
                                  <InputFileComponent
                                    editNode={true}
                                    disabled={disabled}
                                    value={
                                      myData.current.node.template[
                                        templateParam
                                      ].value ?? ""
                                    }
                                    onChange={(value: string | string[]) => {
                                      handleOnNewValue(value, templateParam);
                                    }}
                                    fileTypes={
                                      myData.current.node.template[
                                        templateParam
                                      ].fileTypes
                                    }
                                    suffixes={
                                      myData.current.node.template[
                                        templateParam
                                      ].suffixes
                                    }
                                    onFileChange={(filePath: string) => {
                                      data.node!.template[
                                        templateParam
                                      ].file_path = filePath;
                                    }}
                                  ></InputFileComponent>
                                </div>
                              ) : myData.current.node?.template[templateParam]
                                  .type === "prompt" ? (
                                <div className="mx-auto">
                                  <PromptAreaComponent
                                    readonly={
                                      myData.current.node?.flow ? true : false
                                    }
                                    field_name={templateParam}
                                    editNode={true}
                                    disabled={disabled}
                                    nodeClass={myData.current.node}
                                    setNodeClass={(nodeClass) => {
                                      myData.current.node = nodeClass;
                                    }}
                                    value={
                                      myData.current.node.template[
                                        templateParam
                                      ].value ?? ""
                                    }
                                    onChange={(value: string | string[]) => {
                                      handleOnNewValue(value, templateParam);
                                    }}
                                    id={"prompt-area-edit" + index}
                                  />
                                </div>
                              ) : myData.current.node?.template[templateParam]
                                  .type === "code" ? (
                                <div className="mx-auto">
                                  <CodeAreaComponent
                                    readonly={
                                      myData.current.node?.flow &&
                                      myData.current.node.template[
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
                                      myData.current.node.template[
                                        templateParam
                                      ].value ?? ""
                                    }
                                    onChange={(value: string | string[]) => {
                                      handleOnNewValue(value, templateParam);
                                    }}
                                    id={"code-area-edit" + index}
                                  />
                                </div>
                              ) : myData.current.node?.template[templateParam]
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
                                    myData.current.node?.template[templateParam]
                                      .name
                                  }
                                  enabled={
                                    !myData.current.node?.template[
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
            id={"saveChangesBtn"}
            className="mt-3"
            onClick={() => {
              const newData = cloneDeep(myData.current);
              myData.current = newData;
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
