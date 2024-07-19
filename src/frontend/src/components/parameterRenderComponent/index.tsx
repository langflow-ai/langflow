import { handleOnNewValueType } from "@/CustomNodes/hooks/use-handle-new-value";
import { APIClassType, InputFieldType } from "@/types/api";
import CodeAreaComponent from "../codeAreaComponent";
import DictComponent from "../dictComponent";
import FloatComponent from "../floatComponent";
import InputFileComponent from "../inputFileComponent";
import IntComponent from "../intComponent";
import KeypairListComponent from "../keypairListComponent";
import PromptAreaComponent from "../promptComponent";
import ToggleShadComponent from "../toggleShadComponent";
import { StrRenderComponent } from "./component/strRenderComponent";

function ParameterRenderComponent({
  handleOnNewValue,
  templateData,
  templateValue,
  editNode,
  handleNodeClass,
  nodeClass,
  disabled,
}: {
  handleOnNewValue: handleOnNewValueType;
  templateData: Partial<InputFieldType>;
  templateValue: any;
  editNode: boolean;
  handleNodeClass: (value: any, code?: string, type?: string) => void;
  nodeClass: APIClassType;
  disabled: boolean;
}) {
  const onChange = (value: any) => {
    handleOnNewValue({ value });
  };

  return templateData.type === "str" ? (
    <StrRenderComponent
      templateData={templateData}
      value={templateValue}
      disabled={disabled}
      handleOnNewValue={handleOnNewValue}
      editNode={editNode}
    />
  ) : templateData.type === "NestedDict" ? (
    <DictComponent
      disabled={disabled}
      editNode={editNode}
      value={(templateValue || "").toString() === "{}" ? {} : templateValue}
      onChange={onChange}
      id="editnode-div-dict-input"
    />
  ) : templateData.type === "dict" ? (
    <KeypairListComponent
      disabled={disabled}
      editNode={editNode}
      value={templateValue}
      onChange={onChange}
      isList={templateData.list ?? false}
    />
  ) : templateData.type === "bool" ? (
    <ToggleShadComponent
      id={"toggle-edit-" + templateData.name}
      disabled={disabled}
      enabled={templateValue}
      setEnabled={onChange}
      size="small"
      editNode={editNode}
    />
  ) : templateData.type === "float" ? (
    <FloatComponent
      disabled={disabled}
      editNode={editNode}
      rangeSpec={templateData.rangeSpec}
      value={templateValue ?? ""}
      onChange={onChange}
    />
  ) : templateData.type === "int" ? (
    <IntComponent
      rangeSpec={templateData.rangeSpec}
      id={"edit-int-input-" + templateData.name}
      disabled={disabled}
      editNode={editNode}
      value={templateValue ?? ""}
      onChange={onChange}
    />
  ) : templateData.type === "file" ? (
    <InputFileComponent
      editNode={editNode}
      disabled={disabled}
      value={templateValue ?? ""}
      handleOnNewValue={handleOnNewValue}
      fileTypes={templateData.fileTypes}
    />
  ) : templateData.type === "prompt" ? (
    <PromptAreaComponent
      readonly={nodeClass.flow ? true : false}
      field_name={templateData.key}
      editNode={editNode}
      disabled={disabled}
      nodeClass={nodeClass}
      setNodeClass={handleNodeClass}
      value={templateValue ?? ""}
      onChange={onChange}
      id={"prompt-area-edit-" + templateData.name}
      data-testid={"modal-prompt-input-" + templateData.name}
    />
  ) : templateData.type === "code" ? (
    <CodeAreaComponent
      readonly={nodeClass.flow && templateData.dynamic ? true : false}
      dynamic={templateData.dynamic ?? false}
      setNodeClass={handleNodeClass}
      nodeClass={nodeClass}
      disabled={disabled}
      editNode={editNode}
      value={templateValue ?? ""}
      onChange={onChange}
      id={"code-area-edit" + templateData.name}
    />
  ) : templateData.type === "Any" ? (
    <>-</>
  ) : (
    String(templateValue)
  );
}
