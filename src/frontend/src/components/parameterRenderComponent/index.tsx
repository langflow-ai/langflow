import { handleOnNewValueType } from "@/CustomNodes/hooks/use-handle-new-value";
import { TEXT_FIELD_TYPES } from "@/constants/constants";
import { APIClassType, InputFieldType } from "@/types/api";
import { useMemo } from "react";
import TableNodeComponent from "../TableNodeComponent";
import CodeAreaComponent from "../codeAreaComponent";
import DictComponent from "../dictComponent";
import FloatComponent from "../floatComponent";
import InputFileComponent from "../inputFileComponent";
import IntComponent from "../intComponent";
import KeypairListComponent from "../keypairListComponent";
import LinkComponent from "../linkComponent";
import PromptAreaComponent from "../promptComponent";
import ToggleShadComponent from "../toggleShadComponent";
import { RefreshParameterComponent } from "./component/refreshParameterComponent";
import { StrRenderComponent } from "./component/strRenderComponent";

export function ParameterRenderComponent({
  handleOnNewValue,
  name,
  nodeId,
  templateData,
  templateValue,
  editNode,
  handleNodeClass,
  nodeClass,
  disabled,
}: {
  handleOnNewValue: handleOnNewValueType;
  name: string;
  nodeId: string;
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

  const id = (
    templateData.type +
    "_" +
    (editNode ? "edit_" : "") +
    templateData.name
  ).toLowerCase();

  return useMemo(
    () => (
      <RefreshParameterComponent
        templateData={templateData}
        disabled={disabled}
        nodeId={nodeId}
        editNode={editNode}
        nodeClass={nodeClass}
        handleNodeClass={handleNodeClass}
        name={name}
      >
        {TEXT_FIELD_TYPES.includes(templateData.type ?? "") ? (
          <StrRenderComponent
            templateData={templateData}
            value={templateValue}
            name={name}
            disabled={disabled}
            handleOnNewValue={handleOnNewValue}
            id={id}
            editNode={editNode}
          />
        ) : templateData.type === "NestedDict" ? (
          <DictComponent
            disabled={disabled}
            editNode={editNode}
            value={
              (templateValue || "").toString() === "{}" ? {} : templateValue
            }
            onChange={onChange}
            id={`dict_${id}`}
          />
        ) : templateData.type === "dict" ? (
          <KeypairListComponent
            disabled={disabled}
            editNode={editNode}
            value={templateValue}
            onChange={onChange}
            isList={templateData.list ?? false}
            id={`keypair_${id}`}
          />
        ) : templateData.type === "bool" ? (
          <ToggleShadComponent
            id={`toggle_${id}`}
            disabled={disabled}
            enabled={templateValue}
            setEnabled={onChange}
            size={editNode ? "small" : "large"}
          />
        ) : templateData.type === "link" ? (
          <LinkComponent
            value={templateData}
            onChange={onChange}
            id={`link_${id}`}
          />
        ) : templateData.type === "float" ? (
          <FloatComponent
            disabled={disabled}
            editNode={editNode}
            rangeSpec={templateData.range_spec}
            value={templateValue ?? ""}
            onChange={onChange}
            id={`float_${id}`}
          />
        ) : templateData.type === "int" ? (
          <IntComponent
            rangeSpec={templateData.range_spec}
            id={`int_${id}`}
            disabled={disabled}
            editNode={editNode}
            value={templateValue ?? 0}
            onChange={onChange}
          />
        ) : templateData.type === "file" ? (
          <InputFileComponent
            editNode={editNode}
            disabled={disabled}
            value={templateValue ?? ""}
            handleOnNewValue={handleOnNewValue}
            fileTypes={templateData.fileTypes}
            id={`inputfile_${id}`}
          />
        ) : templateData.type === "prompt" ? (
          <PromptAreaComponent
            readonly={nodeClass.flow ? true : false}
            field_name={name}
            editNode={editNode}
            disabled={disabled}
            nodeClass={nodeClass}
            setNodeClass={handleNodeClass}
            value={templateValue ?? ""}
            onChange={onChange}
            id={`promptarea_${id}`}
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
            id={`codearea_${id}`}
          />
        ) : templateData.type === "Any" ? (
          <>-</>
        ) : templateData.type === "table" ? (
          <TableNodeComponent
            description={templateData.info || "Add or edit data"}
            columns={templateData?.table_schema?.columns}
            onChange={onChange}
            tableTitle={templateData?.display_name ?? "Table"}
            value={templateValue}
          />
        ) : (
          String(templateValue)
        )}
      </RefreshParameterComponent>
    ),
    [templateData, disabled, nodeId, editNode, nodeClass, name, templateValue],
  );
}
