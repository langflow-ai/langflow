import { useMemo, useState } from "react";
import { sortToolModeFields } from "@/CustomNodes/helpers/sort-tool-mode-field";
import getFieldTitle from "@/CustomNodes/utils/get-field-title";
import type { NodeDataType } from "@/types/flow";
import { LANGFLOW_SUPPORTED_TYPES } from "@/constants/constants";
import InspectionPanelField from "./InspectionPanelField";
import { ChevronRight } from "lucide-react";
import { cn } from "@/utils/utils";
import {
  Disclosure,
  DisclosureTrigger,
  DisclosureContent,
} from "@/components/ui/disclosure";

interface InspectionPanelFieldsProps {
  data: NodeDataType;
}

export default function InspectionPanelFields({
  data,
}: InspectionPanelFieldsProps) {
  const [showAdvanced, setShowAdvanced] = useState(false);

  // Separate basic and advanced fields
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

    const basic: string[] = [];
    const advanced: string[] = [];

    allFields.forEach((field) => {
      const template = data.node?.template[field];
      if (template?.advanced) {
        advanced.push(field);
      } else {
        basic.push(field);
      }
    });

    return { basicFields: basic, advancedFields: advanced };
  }, [data.node?.template, data.node?.field_order]);

  if (basicFields.length === 0 && advancedFields.length === 0) {
    return (
      <div className="flex items-center justify-center p-8 text-sm text-muted-foreground">
        No fields available
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
      />
    );
  };

  return (
    <div className="p-1 pb-3">
      {/* Render basic fields */}
      {basicFields.map(renderField)}

      {/* Render advanced fields disclosure */}
      {advancedFields.length > 0 && (
        <Disclosure
          open={showAdvanced}
          onOpenChange={setShowAdvanced}
          className="mt-2"
        >
          <div className="px-3">
          <DisclosureTrigger>
            <div
              className={cn(
                "flex w-full items-center justify-between px-4 py-2 text-xs font-medium text-muted-foreground transition-colors hover:text-foreground",
                "cursor-pointer rounded-md hover:bg-muted/50"
              )}
            >
              <span>Advanced</span>
              <ChevronRight
                className={cn(
                  "h-4 w-4 transition-transform duration-200",
                  showAdvanced && "rotate-90"
                )}
              />
            </div>
          </DisclosureTrigger></div>

          <DisclosureContent>
            <div className="mt-1">
              {advancedFields.map(renderField)}
            </div>
          </DisclosureContent>
        </Disclosure>
      )}
    </div>
  );
}

// Made with Bob
