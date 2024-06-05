import { CustomCellRendererProps } from "ag-grid-react";
import { classNames, cn, isTimeStampString } from "../../utils/utils";
import ArrayReader from "../arrayReaderComponent";
import DateReader from "../dateReaderComponent";
import NumberReader from "../numberReader";
import ObjectRender from "../objectRender";
import StringReader from "../stringReaderComponent";
import { Badge } from "../ui/badge";
import { cloneDeep } from "lodash";
import { type } from "os";
import {
  convertObjToArray,
  convertValuesToNumbers,
  hasDuplicateKeys,
  scapedJSONStringfy,
} from "../../utils/reactflowUtils";
import CodeAreaComponent from "../codeAreaComponent";
import DictComponent from "../dictComponent";
import Dropdown from "../dropdownComponent";
import FloatComponent from "../floatComponent";
import InputFileComponent from "../inputFileComponent";
import InputGlobalComponent from "../inputGlobalComponent";
import InputListComponent from "../inputListComponent";
import IntComponent from "../intComponent";
import KeypairListComponent from "../keypairListComponent";
import PromptAreaComponent from "../promptComponent";
import TextAreaComponent from "../textAreaComponent";
import ToggleShadComponent from "../toggleShadComponent";
import { useState } from "react";
import useFlowStore from "../../stores/flowStore";

export default function TableNodeCellRender({
  node: { data: templateData },
  value: {
    value: templateValue,
    nodeClass,
    handleOnNewValue,
    handleOnChangeDb,
  },
}: CustomCellRendererProps) {
  console.log(
    templateData,
    templateValue,
    nodeClass,
    handleOnNewValue,
    handleOnChangeDb,
  );
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
        if (!templateData.options) {
          return (
            <div className="w-[300px]">
              {templateData?.list ? (
                <InputListComponent
                  componentName={templateData.key ?? undefined}
                  editNode={true}
                  disabled={disabled}
                  value={
                    !templateValue || templateValue === ""
                      ? [""]
                      : templateValue
                  }
                  onChange={(value: string[]) => {
                    handleOnNewValue(value, templateData.key);
                  }}
                />
              ) : templateData.multiline ? (
                <TextAreaComponent
                  id={"textarea-edit-" + templateData.name}
                  data-testid={"textarea-edit-" + templateData.name}
                  disabled={disabled}
                  editNode={true}
                  value={templateData.value ?? ""}
                  onChange={(value: string | string[]) => {
                    handleOnNewValue(value, templateData.key);
                  }}
                />
              ) : (
                <InputGlobalComponent
                  disabled={disabled}
                  editNode={true}
                  onChange={(value) =>
                    handleOnNewValue(value, templateData.key)
                  }
                  setDb={(value) => {
                    handleOnChangeDb(value, templateData.key);
                  }}
                  name={templateData.key}
                  data={templateData}
                />
              )}
            </div>
          );
        } else {
          return (
            <div className="w-[300px]">
              <Dropdown
                editNode={true}
                options={templateData.options}
                onSelect={(value) => handleOnNewValue(value, templateData.key)}
                value={templateData.value ?? "Choose an option"}
                id={"dropdown-edit-" + templateData.name}
              ></Dropdown>
            </div>
          );
        }

      case "NestedDict":
        return (
          <div className="  w-full">
            <DictComponent
              disabled={disabled}
              editNode={true}
              value={templateValue.toString() === "{}" ? {} : templateValue}
              onChange={(newValue) => {
                templateValue = newValue;
                handleOnNewValue(newValue, templateData.key);
              }}
              id="editnode-div-dict-input"
            />
          </div>
        );
        break;

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
                templateData.value?.length === 0 || !templateData.value
                  ? [{ "": "" }]
                  : convertObjToArray(templateValue, templateData.type)
              }
              duplicateKey={errorDuplicateKey}
              onChange={(newValue) => {
                const valueToNumbers = convertValuesToNumbers(newValue);
                templateValue = valueToNumbers;
                setErrorDuplicateKey(hasDuplicateKeys(valueToNumbers));
                handleOnNewValue(valueToNumbers, templateData.key);
              }}
              isList={templateData.list ?? false}
            />
          </div>
        );
        break;

      case "bool":
        return (
          <div className="ml-auto">
            {" "}
            <ToggleShadComponent
              id={"toggle-edit-" + templateData.name}
              disabled={disabled}
              enabled={templateData.value}
              setEnabled={(isEnabled) => {
                handleOnNewValue(isEnabled, templateData.key);
              }}
              size="small"
              editNode={true}
            />
          </div>
        );

      case "float":
        return (
          <div className="w-[300px]">
            <FloatComponent
              disabled={disabled}
              editNode={true}
              rangeSpec={templateData.rangeSpec}
              value={templateData.value ?? ""}
              onChange={(value) => {
                handleOnNewValue(value, templateData.key);
              }}
            />
          </div>
        );
      case "int":
        return (
          <div className="w-[300px]">
            <IntComponent
              rangeSpec={templateData.rangeSpec}
              id={"edit-int-input-" + templateData.name}
              disabled={disabled}
              editNode={true}
              value={templateData.value ?? ""}
              onChange={(value) => {
                handleOnNewValue(value, templateData.key);
              }}
            />
          </div>
        );
        break;

      case "file":
        return (
          <div className="w-[300px]">
            <InputFileComponent
              editNode={true}
              disabled={disabled}
              value={templateData.value ?? ""}
              onChange={(value: string | string[]) => {
                handleOnNewValue(value, templateData.key);
              }}
              fileTypes={templateData.fileTypes}
              onFileChange={(filePath: string) => {
                templateData.file_path = filePath;
              }}
            ></InputFileComponent>
          </div>
        );

      case "prompt":
        return (
          <div className="w-[300px]">
            <PromptAreaComponent
              readonly={nodeClass.flow ? true : false}
              field_name={templateData.key}
              editNode={true}
              disabled={disabled}
              nodeClass={nodeClass}
              setNodeClass={(value) => {
                nodeClass = value;
              }}
              value={templateValue ?? ""}
              onChange={(value: string | string[]) => {
                handleOnNewValue(value, templateData.key);
              }}
              id={"prompt-area-edit-" + templateData.name}
              data-testid={"modal-prompt-input-" + templateData.name}
            />
          </div>
        );
        break;

      case "code":
        return (
          <div className="w-[300px]">
            <CodeAreaComponent
              readonly={nodeClass.flow && templateData.dynamic ? true : false}
              dynamic={templateData.dynamic ?? false}
              setNodeClass={(value) => {
                nodeClass = value;
              }}
              nodeClass={nodeClass}
              disabled={disabled}
              editNode={true}
              value={templateData.value ?? ""}
              onChange={(value: string | string[]) => {
                handleOnNewValue(value, templateData.key);
              }}
              id={"code-area-edit" + templateData.name}
            />
          </div>
        );
        break;
      case "Any":
        return <>-</>;
        break;
      default:
        return String(templateValue);
    }
  }

  return (
    <div className="group flex h-full w-full items-center align-middle">
      {getCellType()}
    </div>
  );
}
