import { useMemo } from "react";
import { getNodeInputColors } from "@/CustomNodes/helpers/get-node-input-colors";
import { getNodeInputColorsName } from "@/CustomNodes/helpers/get-node-input-colors-name";
import { sortToolModeFields } from "@/CustomNodes/helpers/sort-tool-mode-field";
import getFieldTitle from "@/CustomNodes/utils/get-field-title";
import { scapedJSONStringfy } from "@/utils/reactflowUtils";
import NodeInputField from "../NodeInputField";
import { findPrimaryInput } from "./utils";

const RenderInputParameters = ({
  data,
  types,
  isToolMode,
  showNode,
  shownOutputs,
  showHiddenOutputs,
}) => {
  const templateFields = useMemo(() => {
    return Object.keys(data.node?.template || {})
      .filter((templateField) => templateField.charAt(0) !== "_")
      .sort((a, b) =>
        sortToolModeFields(
          a,
          b,
          data.node!.template,
          data.node?.field_order ?? [],
          isToolMode,
        ),
      );
  }, [data.node?.template, data.node?.field_order, isToolMode]);

  const shownTemplateFields = useMemo(() => {
    return templateFields.filter((templateField) => {
      const template = data.node?.template[templateField];
      return (
        template?.show &&
        !template?.advanced &&
        !(template?.tool_mode && isToolMode)
      );
    });
  }, [templateFields, data.node?.template, isToolMode]);

  const memoizedColors = useMemo(() => {
    const colorMap = new Map();

    templateFields.forEach((templateField) => {
      const template = data.node?.template[templateField];
      if (template) {
        // For model type fields, provide default input_types if not set
        const isModelType = template.type === "model";
        const effectiveInputTypes =
          template.input_types && template.input_types.length > 0
            ? template.input_types
            : isModelType
              ? ["LanguageModel"]
              : template.input_types;

        colorMap.set(templateField, {
          colors: getNodeInputColors(effectiveInputTypes, template.type, types),
          colorsName: getNodeInputColorsName(
            effectiveInputTypes,
            template.type,
            types,
          ),
        });
      }
    });

    return colorMap;
  }, [templateFields, types, data.node?.template]);

  const memoizedKeys = useMemo(() => {
    const keyMap = new Map();

    templateFields.forEach((templateField) => {
      const template = data.node?.template[templateField];
      if (template) {
        keyMap.set(
          templateField,
          scapedJSONStringfy({
            inputTypes: template.input_types,
            type: template.type,
            id: data.id,
            fieldName: templateField,
            proxy: template.proxy,
          }),
        );
      }
    });

    return keyMap;
  }, [templateFields, data.id, data.node?.template]);

  const { displayHandleMap, primaryInputFieldName } = useMemo(() => {
    return findPrimaryInput(
      shownTemplateFields,
      data.node?.template ?? {},
      isToolMode,
    );
  }, [shownTemplateFields, data.node?.template, isToolMode]);

  const renderInputParameter = shownTemplateFields.map(
    (templateField: string, idx: number) => {
      const template = data.node?.template[templateField];

      const memoizedColor = memoizedColors.get(templateField);
      const memoizedKey = memoizedKeys.get(templateField);

      // For model type fields, provide default input_types if not set
      const isModelType = template.type === "model";
      const effectiveInputTypes =
        template.input_types && template.input_types.length > 0
          ? template.input_types
          : isModelType
            ? ["LanguageModel"]
            : template.input_types;

      return (
        <NodeInputField
          lastInput={
            !(shownOutputs.length > 0 || showHiddenOutputs) &&
            idx === shownTemplateFields.length - 1
          }
          key={memoizedKey}
          data={data}
          colors={memoizedColor.colors}
          title={getFieldTitle(data.node?.template!, templateField)}
          info={template.info!}
          name={templateField}
          tooltipTitle={effectiveInputTypes?.join("\n") ?? template.type}
          required={template.required}
          id={{
            inputTypes: effectiveInputTypes,
            type: template.type,
            id: data.id,
            fieldName: templateField,
          }}
          type={template.type}
          optionalHandle={effectiveInputTypes}
          proxy={template.proxy}
          showNode={showNode}
          colorName={memoizedColor.colorsName}
          isToolMode={isToolMode && template.tool_mode}
          isPrimaryInput={templateField === primaryInputFieldName}
          displayHandle={displayHandleMap.get(templateField) ?? false}
        />
      );
    },
  );

  return <>{renderInputParameter}</>;
};

export default RenderInputParameters;
