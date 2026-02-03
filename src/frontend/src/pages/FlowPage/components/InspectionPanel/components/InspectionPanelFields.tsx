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
import { shouldRenderInspectionPanelField } from "@/CustomNodes/helpers/parameter-filtering";
import { Separator } from "@/components/ui/separator";

interface InspectionPanelFieldsProps {
  data: NodeDataType;
}

export default function InspectionPanelFields({
  data,
}: InspectionPanelFieldsProps) {
  const [showAdvanced, setShowAdvanced] = useState(false);
  const isToolMode = data.node?.tool_mode;

  // Separate basic and advanced fields
  const { basicFields, advancedFields } = useMemo(() => {
    const allFields = Object.keys(data.node?.template || {})
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

  const renderField = (
    templateField: string,
    showAdvancedButton: boolean = false,
  ) => {
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
        showAdvanced={showAdvancedButton}
      />
    );
  };

  return (
    <div className="pb-2">
      {/* Render basic fields */}
      <div className="px-1">
        {basicFields.map((field) => renderField(field, showAdvanced))}
      </div>

      {/* Render advanced fields disclosure */}
      <Separator className="mt-3" />
      {advancedFields.length > 0 && (
        <Disclosure
          open={showAdvanced}
          onOpenChange={setShowAdvanced}
          className="mt-2 px-1"
        >
          <DisclosureTrigger>
            <div
              className={cn(
                "flex w-full items-center justify-between px-3 py-2 text-xs font-medium text-muted-foreground transition-colors hover:text-foreground",
                "cursor-pointer rounded-md hover:bg-muted/50",
              )}
              data-testid={
                showAdvanced ? "edit-button-close" : "edit-button-modal"
              }
            >
              <span>Advanced</span>
              <ChevronRight
                className={cn(
                  "h-4 w-4 transition-transform duration-200",
                  showAdvanced && "rotate-90",
                )}
              />
            </div>
          </DisclosureTrigger>

          <DisclosureContent>
            <div className="my-1">
              {advancedFields.map((field) => renderField(field, true))}
            </div>
          </DisclosureContent>
        </Disclosure>
      )}
    </div>
  );
}
