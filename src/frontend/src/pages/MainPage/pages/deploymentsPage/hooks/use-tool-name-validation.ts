import { keepPreviousData } from "@tanstack/react-query";
import { useMemo } from "react";
import { useCheckToolNames } from "@/controllers/API/queries/deployments";
import type { ReviewFlowItem } from "../components/step-review-types";

function normalizeWxoName(name: string): string {
  return name.replace(/[\s-]/g, "_").replace(/[^a-zA-Z0-9_]/g, "");
}

interface UseToolNameValidationParams {
  reviewFlows: ReviewFlowItem[];
  selectedInstanceId?: string;
  isEditMode: boolean;
  preExistingFlowIds: Set<string>;
  initialToolNameByFlow: Map<string, string>;
}

export function useToolNameValidation({
  reviewFlows,
  selectedInstanceId,
  isEditMode,
  preExistingFlowIds,
  initialToolNameByFlow,
}: UseToolNameValidationParams) {
  const toolNamesToCheck = useMemo(() => {
    const names: string[] = [];

    for (const item of reviewFlows) {
      const normalized = normalizeWxoName(item.toolName);
      if (!normalized) continue;

      if (isEditMode && preExistingFlowIds.has(item.flowId)) {
        const original = normalizeWxoName(
          initialToolNameByFlow.get(item.flowId) ?? "",
        );
        const normalizedFlowName = normalizeWxoName(item.flowName);

        if (
          normalized.toLowerCase() === original.toLowerCase() ||
          normalized.toLowerCase() === normalizedFlowName.toLowerCase()
        ) {
          continue;
        }
      }

      names.push(normalized);
    }

    return names;
  }, [reviewFlows, isEditMode, preExistingFlowIds, initialToolNameByFlow]);

  const { data: checkNamesData } = useCheckToolNames(
    { providerId: selectedInstanceId ?? "", names: toolNamesToCheck },
    {
      enabled: !!selectedInstanceId && toolNamesToCheck.length > 0,
      placeholderData: keepPreviousData,
    },
  );

  const existingToolNames = useMemo(() => {
    if (!checkNamesData?.existing_names) {
      return new Set<string>();
    }

    return new Set(
      checkNamesData.existing_names.map((name) => name.toLowerCase()),
    );
  }, [checkNamesData]);

  const toolNameErrors = useMemo(() => {
    const errors = new Map<string, string>();
    const batchNames = new Map<string, string>();

    for (const item of reviewFlows) {
      const normalized = normalizeWxoName(item.toolName).toLowerCase();
      if (!normalized) continue;

      const firstFlowId = batchNames.get(normalized);
      if (firstFlowId) {
        errors.set(item.flowId, "Duplicate tool name within this deployment");
        if (!errors.has(firstFlowId)) {
          errors.set(firstFlowId, "Duplicate tool name within this deployment");
        }
      } else {
        batchNames.set(normalized, item.flowId);
      }

      if (!errors.has(item.flowId) && existingToolNames.has(normalized)) {
        let skipProviderCheck = false;

        if (isEditMode && preExistingFlowIds.has(item.flowId)) {
          const original = normalizeWxoName(
            initialToolNameByFlow.get(item.flowId) ?? "",
          ).toLowerCase();
          skipProviderCheck =
            normalized === original ||
            normalized === normalizeWxoName(item.flowName).toLowerCase();
        }

        if (!skipProviderCheck) {
          errors.set(
            item.flowId,
            "Edit tool name (already exists in provider)",
          );
        }
      }
    }

    return errors;
  }, [
    reviewFlows,
    existingToolNames,
    isEditMode,
    preExistingFlowIds,
    initialToolNameByFlow,
  ]);

  return {
    toolNameErrors,
  };
}
