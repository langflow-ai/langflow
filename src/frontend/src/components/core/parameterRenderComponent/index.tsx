import { handleOnNewValueType } from "@/CustomNodes/hooks/use-handle-new-value";
import { TEXT_FIELD_TYPES } from "@/constants/constants";
import { APIClassType, InputFieldType } from "@/types/api";
import { memo, useCallback, useMemo } from "react";
import { InputProps } from "./types";

// Import components
import TableNodeComponent from "@/components/core/parameterRenderComponent/components/TableNodeComponent";
import CodeAreaComponent from "@/components/core/parameterRenderComponent/components/codeAreaComponent";
import SliderComponent from "@/components/core/parameterRenderComponent/components/sliderComponent";
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

const MemoizedTableNode = memo(TableNodeComponent);
const MemoizedCodeArea = memo(CodeAreaComponent);
const MemoizedSlider = memo(SliderComponent);
const MemoizedDict = memo(DictComponent);
const MemoizedEmpty = memo(EmptyParameterComponent);
const MemoizedFloat = memo(FloatComponent);
const MemoizedInputFile = memo(InputFileComponent);
const MemoizedInputList = memo(InputListComponent);
const MemoizedInt = memo(IntComponent);
const MemoizedKeypairList = memo(KeypairListComponent);
const MemoizedLink = memo(LinkComponent);
const MemoizedMultiselect = memo(MultiselectComponent);
const MemoizedPromptArea = memo(PromptAreaComponent);
const MemoizedStrRender = memo(StrRenderComponent);
const MemoizedToggleShad = memo(ToggleShadComponent);

interface ParameterRenderProps {
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
}

export const ParameterRenderComponent = memo(function ParameterRenderComponent({
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
}: ParameterRenderProps) {
  const id = useMemo(
    () =>
      (
        templateData.type +
        "_" +
        (editNode ? "edit_" : "") +
        templateData.name
      ).toLowerCase(),
    [templateData.type, templateData.name, editNode],
  );

  const baseInputProps = useMemo(
    () => ({
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
    }),
    [
      id,
      templateValue,
      editNode,
      handleOnNewValue,
      disabled,
      nodeClass,
      handleNodeClass,
      templateData.readonly,
      placeholder,
      isToolMode,
    ],
  );

  const renderComponent = useCallback((): React.ReactElement<InputProps> => {
    if (TEXT_FIELD_TYPES.includes(templateData.type ?? "")) {
      if (templateData.list) {
        if (!templateData.options) {
          return (
            <MemoizedInputList
              {...baseInputProps}
              componentName={name}
              id={`inputlist_${id}`}
            />
          );
        }
        if (!!templateData.options) {
          return (
            <MemoizedMultiselect
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
        <MemoizedStrRender
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
          <MemoizedDict
            name={name ?? ""}
            {...baseInputProps}
            id={`dict_${id}`}
          />
        );
      case "dict":
        return (
          <MemoizedKeypairList
            {...baseInputProps}
            isList={templateData.list ?? false}
            id={`keypair_${id}`}
          />
        );
      case "bool":
        return (
          <MemoizedToggleShad
            size="medium"
            {...baseInputProps}
            id={`toggle_${id}`}
          />
        );
      case "link":
        return (
          <MemoizedLink
            {...baseInputProps}
            icon={templateData.icon}
            text={templateData.text}
            id={`link_${id}`}
          />
        );
      case "float":
        return (
          <MemoizedFloat
            {...baseInputProps}
            id={`float_${id}`}
            rangeSpec={templateData.range_spec}
          />
        );
      case "int":
        return (
          <MemoizedInt
            {...baseInputProps}
            rangeSpec={templateData.range_spec}
            id={`int_${id}`}
          />
        );
      case "file":
        return (
          <MemoizedInputFile
            {...baseInputProps}
            fileTypes={templateData.fileTypes}
            id={`inputfile_${id}`}
          />
        );
      case "prompt":
        return (
          <MemoizedPromptArea
            {...baseInputProps}
            readonly={!!nodeClass.flow}
            field_name={name}
            id={`promptarea_${id}`}
          />
        );
      case "code":
        return <MemoizedCodeArea {...baseInputProps} id={`codearea_${id}`} />;
      case "table":
        return (
          <MemoizedTableNode
            {...baseInputProps}
            description={templateData.info || "Add or edit data"}
            columns={templateData?.table_schema?.columns}
            tableTitle={templateData?.display_name ?? "Table"}
            table_options={templateData?.table_options}
            trigger_icon={templateData?.trigger_icon}
            trigger_text={templateData?.trigger_text}
          />
        );
      case "slider":
        return (
          <MemoizedSlider
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
        return <MemoizedEmpty {...baseInputProps} />;
    }
  }, [templateData, baseInputProps, name, id, nodeClass.flow]);

  return (
    <RefreshParameterComponent
      templateData={templateData}
      disabled={disabled}
      nodeId={nodeId}
      editNode={editNode}
      nodeClass={nodeClass}
      handleNodeClass={handleNodeClass}
      name={name}
    >
      {useMemo(() => renderComponent(), [renderComponent])}
    </RefreshParameterComponent>
  );
});
