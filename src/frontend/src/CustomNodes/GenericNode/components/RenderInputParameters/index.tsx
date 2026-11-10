import { useMemo } from "react";
import { useTranslation } from "react-i18next";
import { getNodeInputColors } from "@/CustomNodes/helpers/get-node-input-colors";
import { getNodeInputColorsName } from "@/CustomNodes/helpers/get-node-input-colors-name";
import {
  isCanvasVisible,
  isInternalField,
} from "@/CustomNodes/helpers/parameter-filtering";
import { sortToolModeFields } from "@/CustomNodes/helpers/sort-tool-mode-field";
import getFieldTitle from "@/CustomNodes/utils/get-field-title";
import { questionHandleTitle } from "@/components/core/parameterRenderComponent/components/decision-questions/decision-questions-modal";
import QuestionHandle from "@/components/core/parameterRenderComponent/components/decision-questions/question-handle";
import useFlowStore from "@/stores/flowStore";
import {
  questionConnectionFields,
  scapedJSONStringfy,
} from "@/utils/reactflowUtils";
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
  const { t } = useTranslation();
  const edges = useFlowStore((state) => state.edges);

  const templateFields = useMemo(() => {
    return Object.keys(data.node?.template || {})
      .filter((templateField) => !isInternalField(templateField))
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
      return isCanvasVisible(template, isToolMode);
    });
  }, [templateFields, data.node?.template, isToolMode]);

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
      data.id,
      edges,
    );
  }, [shownTemplateFields, data.node?.template, isToolMode, data.id, edges]);

  // A question list draws its questions' handles on its cards, which a minimized node hides,
  // so there they join the node's other handles.
  const questionHandles = useMemo(
    () =>
      showNode
        ? []
        : questionConnectionFields(data.node?.template ?? {}, isToolMode),
    [showNode, data.node?.template, isToolMode],
  );

  // LE-1810 (T8): a minimized node still shows ALL its input handles —
  // each one gets a distinct vertical offset on the collapsed card.
  const handleFields = useMemo(
    () => [
      ...shownTemplateFields.filter(
        (templateField) => displayHandleMap.get(templateField) ?? false,
      ),
      ...questionHandles.map(({ fieldName }) => fieldName),
    ],
    [shownTemplateFields, displayHandleMap, questionHandles],
  );
  const minimizedHandleTopAt = (handleIdx: number) =>
    `${(((handleIdx + 1) / (handleFields.length + 1)) * 100).toFixed(2)}%`;

  const renderInputParameter = shownTemplateFields.map(
    (templateField: string, idx: number) => {
      const template = data.node?.template[templateField];

      const memoizedColor = memoizedColors.get(templateField);
      const memoizedKey = memoizedKeys.get(templateField);
      const handleIdx = handleFields.indexOf(templateField);

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
          showNode={showNode}
          colorName={memoizedColor.colorsName}
          isToolMode={isToolMode && template.tool_mode}
          isPrimaryInput={templateField === primaryInputFieldName}
          displayHandle={displayHandleMap.get(templateField) ?? false}
          minimizedHandleTop={
            handleIdx === -1 ? undefined : minimizedHandleTopAt(handleIdx)
          }
        />
      );
    },
  );

  // LE-1810 (B05 polish): with several handles on a collapsed card the
  // percentage offsets land too close together — an invisible spacer grows
  // the card so each handle gets breathing room (~18px per handle).
  const minimizedSpacer =
    !showNode && handleFields.length > 1 ? (
      <div
        aria-hidden="true"
        data-testid="minimized-handle-spacer"
        style={{ height: `${(handleFields.length + 1) * 18}px` }}
      />
    ) : null;

  return (
    <>
      {minimizedSpacer}
      {renderInputParameter}
      {questionHandles.map(({ text, fieldName, number }) => (
        <QuestionHandle
          key={fieldName}
          nodeId={data.id}
          fieldName={fieldName}
          field={data.node!.template[fieldName]}
          title={questionHandleTitle(t, number, text)}
          minimizedHandleTop={minimizedHandleTopAt(
            handleFields.indexOf(fieldName),
          )}
        />
      ))}
    </>
  );
};

export default RenderInputParameters;
