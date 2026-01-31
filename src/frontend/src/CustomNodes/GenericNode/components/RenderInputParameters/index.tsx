import { useMemo } from "react";
import { getNodeInputColors } from "@/CustomNodes/helpers/get-node-input-colors";
import { getNodeInputColorsName } from "@/CustomNodes/helpers/get-node-input-colors-name";
import { sortToolModeFields } from "@/CustomNodes/helpers/sort-tool-mode-field";
import getFieldTitle from "@/CustomNodes/utils/get-field-title";
import { scapedJSONStringfy } from "@/utils/reactflowUtils";
import NodeInputField from "../NodeInputField";
import { ENABLE_INSPECTION_PANEL } from "@/customization/feature-flags";
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

      if (!ENABLE_INSPECTION_PANEL) {
        return (
          template?.show &&
          !template?.advanced &&
          !(template?.tool_mode && isToolMode)
        );
      }

      // Basic visibility check
      if (
        !template?.show ||
        template?.advanced ||
        (template?.tool_mode && isToolMode)
      ) {
        return false;
      }

      return true;
    });
  }, [templateFields, data.node?.template, isToolMode]);

  // Separate list for fields that should be visually displayed
  const visuallyShownFields = useMemo(() => {
    if (!ENABLE_INSPECTION_PANEL) {
      return shownTemplateFields;
    }

    return shownTemplateFields.filter((templateField) => {
      const template = data.node?.template[templateField];
      // Only show fields that have handles (input_types)
      const hasHandle = template.input_types && template.input_types.length > 0;
      return hasHandle;
    });
  }, [shownTemplateFields, data.node?.template]);

  const memoizedColors = useMemo(() => {
    const colorMap = new Map();

    templateFields.forEach((templateField) => {
      const template = data.node?.template[templateField];
      if (template) {
        colorMap.set(templateField, {
          colors: getNodeInputColors(
            template.input_types,
            template.type,
            types,
          ),
          colorsName: getNodeInputColorsName(
            template.input_types,
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

      // Check if this field should be visually displayed
      const shouldDisplay = visuallyShownFields.includes(templateField);

      return (
        <NodeInputField
          lastInput={
            !(shownOutputs.length > 0 || showHiddenOutputs) &&
            idx === visuallyShownFields.length - 1 &&
            shouldDisplay
          }
          key={memoizedKey}
          data={data}
          colors={memoizedColor.colors}
          title={getFieldTitle(data.node?.template!, templateField)}
          info={template.info!}
          name={templateField}
          tooltipTitle={template.input_types?.join("\n") ?? template.type}
          required={template.required}
          id={{
            inputTypes: template.input_types,
            type: template.type,
            id: data.id,
            fieldName: templateField,
          }}
          type={template.type}
          optionalHandle={template.input_types}
          proxy={template.proxy}
          showNode={showNode && shouldDisplay}
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
