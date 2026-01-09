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
  // Separate basic and advanced fields, excluding handle-only fields
  const { basicFields, advancedFields } = useMemo(() => {
    const allFields = Object.keys(data.node?.template || {})
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

        // Filter out handle-only fields (fields that are not in LANGFLOW_SUPPORTED_TYPES)
        // These are fields that only serve as connection points without actual input components
        const isHandleOnly = !LANGFLOW_SUPPORTED_TYPES.has(template.type ?? "");
        
        return !isHandleOnly;
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

    const basic: string[] = [];
    const advanced: string[] = [];

    allFields.forEach((field) => {
      const template = data.node?.template[field];
      if (template?.advanced === true) {
        advanced.push(field);
      } else {
        basic.push(field);
      }
    });

    return { basicFields: basic, advancedFields: advanced };
  }, [data.node?.template, data.node?.field_order]);

  const allFields = [...basicFields, ...advancedFields];

  if (allFields.length === 0) {
    return (
      <div className="flex items-center justify-center p-8 text-sm text-muted-foreground">
        No fields available
      </div>
    );
  }

  return (
    <div className="space-y-2 p-3">
      {/* Basic fields first */}
      {basicFields.length > 0 && (
        <div className="space-y-2">
          {basicFields.map((templateField: string) => {
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
      )}

      {/* Advanced fields at the bottom */}
      {advancedFields.length > 0 && (
        <>
          {basicFields.length > 0 && (
            <div className="border-t pt-4">
              <div className="mb-4 text-xs font-semibold uppercase text-muted-foreground">
                Advanced Settings
              </div>
            </div>
          )}
          <div className="space-y-2">
            {advancedFields.map((templateField: string) => {
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
        </>
      )}
    </div>
  );
}

// Made with Bob
