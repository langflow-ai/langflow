import { handleOnNewValueType } from "@/CustomNodes/hooks/use-handle-new-value";
import TableNodeComponent from "@/components/core/parameterRenderComponent/components/TableNodeComponent";
import CodeAreaComponent from "@/components/core/parameterRenderComponent/components/codeAreaComponent";
import SliderComponent from "@/components/core/parameterRenderComponent/components/sliderComponent";
import { TEXT_FIELD_TYPES } from "@/constants/constants";
import { APIClassType, InputFieldType } from "@/types/api";
import { useMemo } from "react";
import DictComponent from "./components/dictComponent";
import { EmptyParameterComponent } from "./components/emptyParameterComponent";
import FloatComponent from "./components/floatComponent";
import InputFileComponent from "./components/inputFileComponent";
import InputListComponent from "./components/inputListComponent";
import IntComponent from "./components/intComponent";
import KeypairListComponent from "./components/keypairListComponent";
import LinkComponent from "./components/linkComponent";
import MultiselectComponent from "./components/multiselectComponent";
import PromptAreaComponent from "./components/promptComponent";
import { RefreshParameterComponent } from "./components/refreshParameterComponent";
import { StrRenderComponent } from "./components/strRenderComponent";
import ToggleShadComponent from "./components/toggleShadComponent";
import { InputProps } from "./types";

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
  placeholder,
  isToolMode,
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
  placeholder?: string;
  isToolMode?: boolean;
}) {
  const id = (
    templateData.type +
    "_" +
    (editNode ? "edit_" : "") +
    templateData.name
  ).toLowerCase();

  const renderComponent = (): React.ReactElement<InputProps> => {
    const baseInputProps: InputProps = {
      id,
      value: templateValue,
      editNode,
      handleOnNewValue,
      disabled,
      nodeClass,
      handleNodeClass,
      readonly: templateData.readonly,
      placeholder,
      isToolMode,
    };
    if (TEXT_FIELD_TYPES.includes(templateData.type ?? "")) {
      if (templateData.list) {
        if (!templateData.options) {
          return (
            <InputListComponent
              {...baseInputProps}
              componentName={name}
              id={`inputlist_${id}`}
            />
          );
        }
        if (!!templateData.options) {
          return (
            <MultiselectComponent
              {...baseInputProps}
              combobox={templateData.combobox}
              options={
                (Array.isArray(templateData.options)
                  ? templateData.options
                  : [templateData.options]) || []
              }
              id={`multiselect_${id}`}
            />
          );
        }
      }
      return (
        <StrRenderComponent
          {...baseInputProps}
          templateData={templateData}
          name={name}
          display_name={templateData.display_name ?? ""}
          editNode={editNode}
        />
      );
    }
    switch (templateData.type) {
      case "NestedDict":
        return (
          <DictComponent
            name={name ?? ""}
            {...baseInputProps}
            id={`dict_${id}`}
          />
        );
      case "dict":
        return (
          <KeypairListComponent
            {...baseInputProps}
            isList={templateData.list ?? false}
            id={`keypair_${id}`}
          />
        );
      case "bool":
        return (
          <ToggleShadComponent
            size="medium"
            {...baseInputProps}
            id={`toggle_${id}`}
          />
        );
      case "link":
        return (
          <LinkComponent
            {...baseInputProps}
            icon={templateData.icon}
            text={templateData.text}
            id={`link_${id}`}
          />
        );
      case "float":
        return (
          <FloatComponent
            {...baseInputProps}
            id={`float_${id}`}
            rangeSpec={templateData.range_spec}
          />
        );
      case "int":
        return (
          <IntComponent
            {...baseInputProps}
            rangeSpec={templateData.range_spec}
            id={`int_${id}`}
          />
        );
      case "file":
        return (
          <InputFileComponent
            {...baseInputProps}
            fileTypes={templateData.fileTypes}
            id={`inputfile_${id}`}
          />
        );
      case "prompt":
        return (
          <PromptAreaComponent
            {...baseInputProps}
            readonly={!!nodeClass.flow}
            field_name={name}
            id={`promptarea_${id}`}
          />
        );
      case "code":
        return <CodeAreaComponent {...baseInputProps} id={`codearea_${id}`} />;
      case "table":
        return (
          <TableNodeComponent
            {...baseInputProps}
            description={templateData.info || "Add or edit data"}
            columns={templateData?.table_schema?.columns}
            tableTitle={templateData?.display_name ?? "Table"}
          />
        );
      case "slider":
        return (
          <SliderComponent
            {...baseInputProps}
            value={templateValue}
            rangeSpec={templateData.range_spec}
            minLabel={templateData?.min_label}
            maxLabel={templateData?.max_label}
            minLabelIcon={templateData?.min_label_icon}
            maxLabelIcon={templateData?.max_label_icon}
            sliderButtons={templateData?.slider_buttons}
            sliderButtonsOptions={templateData?.slider_buttons_options}
            sliderInput={templateData?.slider_input}
            id={`slider_${id}`}
          />
        );
      default:
        return <EmptyParameterComponent {...baseInputProps} />;
    }
  };

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
        {renderComponent()}
      </RefreshParameterComponent>
    ),
    [templateData, disabled, nodeId, editNode, nodeClass, name, templateValue],
  );
}
