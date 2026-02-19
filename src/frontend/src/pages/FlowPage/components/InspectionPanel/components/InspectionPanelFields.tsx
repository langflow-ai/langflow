import { useMemo } from "react";
import { sortToolModeFields } from "@/CustomNodes/helpers/sort-tool-mode-field";
import getFieldTitle from "@/CustomNodes/utils/get-field-title";
import type { NodeDataType } from "@/types/flow";
import InspectionPanelField from "./InspectionPanelField";
import InspectionPanelEditField from "./InspectionPanelEditField";
import {
  shouldRenderInspectionPanelField,
  isInternalField,
  isCodeField,
  isHandleInput,
  isToolModeEnabled,
} from "@/CustomNodes/helpers/parameter-filtering";
import { cn } from "@/utils/utils";
import ForwardedIconComponent from "@/components/common/genericIconComponent";

interface InspectionPanelFieldsProps {
  data: NodeDataType;
  isEditingFields?: boolean;
}

export default function InspectionPanelFields({
  data,
  isEditingFields = false,
}: InspectionPanelFieldsProps) {
  const isToolMode = data.node?.tool_mode;

  // Get all editable fields (for edit mode)
  const allEditableFields = useMemo(() => {
    return Object.keys(data.node?.template || {})
      .filter((templateField) => {
        const template = data.node?.template[templateField];
        if (isInternalField(templateField)) return false;
        if (!template?.show) return false;
        if (isCodeField(templateField, template)) return false;
        if (isToolModeEnabled(template) && isToolMode) return false;
        return true;
      })
      .sort((a, b) =>
        sortToolModeFields(
          a,
          b,
          data.node!.template,
          data.node?.field_order ?? [],
          false,
        ),
      );
  }, [data.node?.template, data.node?.field_order, isToolMode]);

  // Get only advanced fields (for normal mode)
  const advancedFields = useMemo(() => {
    return Object.keys(data.node?.template || {})
      .filter((templateField) => {
        const template = data.node?.template[templateField];
        return shouldRenderInspectionPanelField(
          templateField,
          template,
          isToolMode,
        );
      })
      .sort((a, b) =>
        sortToolModeFields(
          a,
          b,
          data.node!.template,
          data.node?.field_order ?? [],
          false,
        ),
      );
  }, [data.node?.template, data.node?.field_order, isToolMode]);

  // Edit mode - show all fields with simplified edit UI
  if (isEditingFields) {
    if (allEditableFields.length === 0) {
      return (
        <div className="flex items-center justify-center p-8 text-sm text-muted-foreground">
          No editable fields
        </div>
      );
    }

    return (
      <div className="pb-2">
        <div className="px-1">
          {allEditableFields.map((templateField) => {
            const template = data.node?.template[templateField];
            return (
              <InspectionPanelEditField
                key={`${data.id}-${templateField}-edit`}
                data={data}
                name={templateField}
                title={getFieldTitle(data.node?.template!, templateField)}
                description={template.info || ""}
                isOnCanvas={!template.advanced}
              />
            );
          })}
        </div>
      </div>
    );
  }

  // Normal mode - show only advanced fields with full input UI
  if (advancedFields.length === 0) {
    return (
      <div className="flex flex-col gap-2 items-center justify-center p-10 pb-12 text-sm text-muted-foreground">
        <ForwardedIconComponent
          name="Settings2"
          className="text-input w-6 h-6"
        />
        No advanced settings
      </div>
    );
  }

  const renderField = (templateField: string) => {
    const template = data.node?.template[templateField];

    return (
      <InspectionPanelField
        key={`${data.id}-${templateField}`}
        data={data}
        title={getFieldTitle(data.node?.template!, templateField)}
        info={template.info!}
        name={templateField}
        required={template.required}
        id={{
          inputTypes: template.input_types,
          type: template.type,
          id: data.id,
          fieldName: templateField,
        }}
        proxy={template.proxy}
        showNode={true}
        isToolMode={false}
        showAdvanced={false}
      />
    );
  };

  return (
    <div className="pb-2">
      <div className="px-1">
        {advancedFields.map((field) => renderField(field))}
      </div>
    </div>
  );
}
