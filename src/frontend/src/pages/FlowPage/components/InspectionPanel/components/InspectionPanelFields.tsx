import { useMemo } from "react";
import { sortToolModeFields } from "@/CustomNodes/helpers/sort-tool-mode-field";
import getFieldTitle from "@/CustomNodes/utils/get-field-title";
import type { NodeDataType } from "@/types/flow";
import { LANGFLOW_SUPPORTED_TYPES } from "@/constants/constants";
import InspectionPanelField from "./InspectionPanelField";

interface InspectionPanelFieldsProps {
  data: NodeDataType;
}

export default function InspectionPanelFields({
  data,
}: InspectionPanelFieldsProps) {
  // Get all fields in one list - show ALL fields in Inspection Panel
  const allFields = useMemo(() => {
    return Object.keys(data.node?.template || {})
      .filter((templateField) => {
        const template = data.node?.template[templateField];

        // Filter out fields that shouldn't be shown
        if (
          templateField.charAt(0) === "_" ||
          !template?.show ||
          (templateField === "code" && template.type === "code") ||
          (templateField.includes("code") && template.proxy)
        ) {
          return false;
        }

        // Filter out fields that are just handles (HandleInput type)
        // These are fields that only serve as connection points
        if (template._input_type === "HandleInput") {
          return false;
        }

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
  }, [data.node?.template, data.node?.field_order]);

  if (allFields.length === 0) {
    return (
      <div className="flex items-center justify-center p-8 text-sm text-muted-foreground">
        No fields available
      </div>
    );
  }

  return (
    <div className="space-y-2 p-2">
      {allFields.map((templateField: string) => {
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
          />
        );
      })}
    </div>
  );
}

// Made with Bob
