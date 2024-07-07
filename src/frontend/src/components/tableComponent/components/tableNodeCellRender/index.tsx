import { CustomCellRendererProps } from "ag-grid-react";
import { cloneDeep } from "lodash";
import { useState } from "react";
import useFlowStore from "../../../../stores/flowStore";
import { APIClassType } from "../../../../types/api";
import {
  convertObjToArray,
  convertValuesToNumbers,
  hasDuplicateKeys,
  scapedJSONStringfy,
} from "../../../../utils/reactflowUtils";
import { classNames } from "../../../../utils/utils";
import CodeAreaComponent from "../../../codeAreaComponent";
import DictComponent from "../../../dictComponent";
import Dropdown from "../../../dropdownComponent";
import FloatComponent from "../../../floatComponent";
import InputFileComponent from "../../../inputFileComponent";
import InputGlobalComponent from "../../../inputGlobalComponent";
import InputListComponent from "../../../inputListComponent";
import IntComponent from "../../../intComponent";
import KeypairListComponent from "../../../keypairListComponent";
import PromptAreaComponent from "../../../promptComponent";
import TextAreaComponent from "../../../textAreaComponent";
import ToggleShadComponent from "../../../toggleShadComponent";
import { renderStrType } from "./cellTypeStr";

export default function TableNodeCellRender({
  node: { data },
  value: {
    value,
    nodeClass,
    handleOnNewValue: handleOnNewValueNode,
    handleNodeClass,
  },
}: CustomCellRendererProps) {
  const handleOnNewValue = (newValue: any, name: string, dbValue?: boolean) => {
    handleOnNewValueNode(newValue, name, dbValue);
    setTemplateData((old) => {
      let newData = cloneDeep(old);
      newData.value = newValue;
      if (dbValue !== undefined) {
        newData.load_from_db = newValue;
      }
      return newData;
    });
    setTemplateValue(newValue);
  };
  const setNodeClass = (value: APIClassType, code?: string, type?: string) => {
    handleNodeClass(value, templateData.key, code, type);
  };

  const [templateValue, setTemplateValue] = useState(value);
  const [templateData, setTemplateData] = useState(data);
  const [errorDuplicateKey, setErrorDuplicateKey] = useState(false);
  const edges = useFlowStore((state) => state.edges);

  const id = {
    inputTypes: templateData.input_types,
    type: templateData.type,
    id: nodeClass.id,
    fieldName: templateData.key,
  };
  const disabled =
    edges.some(
      (edge) =>
        edge.targetHandle ===
        scapedJSONStringfy(
          templateData.proxy
            ? {
                ...id,
                proxy: templateData.proxy,
              }
            : id,
        ),
    ) ?? false;
  function getCellType() {
    switch (templateData.type) {
      case "str":
        return renderStrType({
          templateData,
          templateValue,
          disabled,
          handleOnNewValue,
        });

      case "NestedDict":
        return (
          <DictComponent
            disabled={disabled}
            editNode={true}
            value={
              (templateValue || "").toString() === "{}" ? {} : templateValue
            }
            onChange={(newValue) => {
              handleOnNewValue(newValue, templateData.key);
            }}
            id="editnode-div-dict-input"
          />
        );

      case "dict":
        return (
          <div
            className={classNames(
              "max-h-48 w-full overflow-auto custom-scroll",
              templateValue?.length > 1 ? "my-3" : "",
            )}
          >
            <KeypairListComponent
              disabled={disabled}
              editNode={true}
              value={
                Object.keys(templateValue || {})?.length === 0 || !templateValue
                  ? [{ "": "" }]
                  : convertObjToArray(templateValue, templateData.type)
              }
              duplicateKey={errorDuplicateKey}
              onChange={(newValue) => {
                const valueToNumbers = convertValuesToNumbers(newValue);
                setErrorDuplicateKey(hasDuplicateKeys(valueToNumbers));
                handleOnNewValue(valueToNumbers, templateData.key);
              }}
              isList={templateData.list ?? false}
            />
          </div>
        );

      case "bool":
        return (
          <ToggleShadComponent
            id={"toggle-edit-" + templateData.name}
            disabled={disabled}
            enabled={templateValue}
            setEnabled={(isEnabled) => {
              handleOnNewValue(isEnabled, templateData.key);
            }}
            size="small"
            editNode={true}
          />
        );

      case "float":
        return (
          <FloatComponent
            disabled={disabled}
            editNode={true}
            rangeSpec={templateData.rangeSpec}
            value={templateValue ?? ""}
            onChange={(value) => {
              handleOnNewValue(value, templateData.key);
            }}
          />
        );
      case "int":
        return (
          <IntComponent
            rangeSpec={templateData.rangeSpec}
            id={"edit-int-input-" + templateData.name}
            disabled={disabled}
            editNode={true}
            value={templateValue ?? ""}
            onChange={(value) => {
              handleOnNewValue(value, templateData.key);
            }}
          />
        );

      case "file":
        return (
          <InputFileComponent
            editNode={true}
            disabled={disabled}
            value={templateValue ?? ""}
            onChange={(value: string | string[]) => {
              handleOnNewValue(value, templateData.key);
            }}
            fileTypes={templateData.fileTypes}
            onFileChange={(filePath: string) => {
              templateData.file_path = filePath;
            }}
          />
        );

      case "prompt":
        return (
          <PromptAreaComponent
            readonly={nodeClass.flow ? true : false}
            field_name={templateData.key}
            editNode={true}
            disabled={disabled}
            nodeClass={nodeClass}
            setNodeClass={setNodeClass}
            value={templateValue ?? ""}
            onChange={(value: string | string[]) => {
              handleOnNewValue(value, templateData.key);
            }}
            id={"prompt-area-edit-" + templateData.name}
            data-testid={"modal-prompt-input-" + templateData.name}
          />
        );

      case "code":
        return (
          <CodeAreaComponent
            readonly={nodeClass.flow && templateData.dynamic ? true : false}
            dynamic={templateData.dynamic ?? false}
            setNodeClass={setNodeClass}
            nodeClass={nodeClass}
            disabled={disabled}
            editNode={true}
            value={templateValue ?? ""}
            onChange={(value: string | string[]) => {
              handleOnNewValue(value, templateData.key);
            }}
            id={"code-area-edit" + templateData.name}
          />
        );
      case "Any":
        return <>-</>;
      default:
        return String(templateValue);
    }
  }

  return (
    <div className="group mx-auto flex h-full w-[300px] items-center justify-center py-2.5">
      {getCellType()}
    </div>
  );
}
