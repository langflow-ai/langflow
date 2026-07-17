import { useMemo } from "react";
import { useTranslation } from "react-i18next";
import { isManageableParameter } from "@/CustomNodes/helpers/parameter-filtering";
import { sortToolModeFields } from "@/CustomNodes/helpers/sort-tool-mode-field";
import getFieldTitle from "@/CustomNodes/utils/get-field-title";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import type { NodeDataType } from "@/types/flow";
import InspectionPanelParameterRow from "./InspectionPanelParameterRow";

interface InspectionPanelFieldsProps {
  data: NodeDataType;
}

export default function InspectionPanelFields({
  data,
}: InspectionPanelFieldsProps) {
  const { t } = useTranslation();
  const isToolMode = data.node?.tool_mode;

  // LE-1810: the panel manages parameters instead of editing values, so it
  // lists every manageable parameter — the ones shown on the node first,
  // then the hidden (advanced) ones — each with add/remove and API actions.
  const manageableFields = useMemo(() => {
    const template = data.node?.template || {};
    return Object.keys(template)
      .filter((templateField) => {
        if (
          data.type === "APIRequest" &&
          templateField === "body" &&
          data.node?.template?.method?.value === "GET"
        )
          return false;
        return isManageableParameter(
          templateField,
          template[templateField],
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
  }, [data.node?.template, data.node?.field_order, data.type, isToolMode]);

  const orderedFields = useMemo(() => {
    const onCanvas = manageableFields.filter(
      (field) => !(data.node?.template[field]?.advanced ?? false),
    );
    const offCanvas = manageableFields.filter(
      (field) => data.node?.template[field]?.advanced ?? false,
    );
    return [...onCanvas, ...offCanvas];
  }, [manageableFields, data.node?.template]);

  if (orderedFields.length === 0) {
    return (
      <div className="flex flex-col gap-2 items-center justify-center p-10 pb-12 text-sm text-muted-foreground">
        <ForwardedIconComponent
          name="Settings2"
          className="text-input w-6 h-6"
        />
        {t("inspectionPanel.noParameters")}
      </div>
    );
  }

  return (
    <div className="pb-2">
      <div className="px-1">
        {orderedFields.map((templateField) => (
          <InspectionPanelParameterRow
            key={`${data.id}-${templateField}`}
            data={data}
            name={templateField}
            title={getFieldTitle(data.node?.template!, templateField)}
          />
        ))}
      </div>
    </div>
  );
}
