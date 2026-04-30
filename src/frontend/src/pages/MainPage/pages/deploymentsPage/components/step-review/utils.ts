import type { ConnectionItem } from "../../types";
import { getDefaultDeploymentToolName } from "../../types";
import type { ReviewFlowItem } from "./types";

export function normalizeWxoName(value: string): string {
  return value.replace(/[\s-]/g, "_").replace(/[^a-zA-Z0-9_]/g, "");
}

function getToolNameForReview(
  toolNameByFlow: Map<string, string>,
  attachmentKey: string,
  flowId: string,
  items: Array<{ attachmentKey: string; flowId: string }>,
) {
  const strictValue = toolNameByFlow.get(attachmentKey)?.trim();
  if (strictValue) {
    return strictValue;
  }

  const flowVersionCount = items.filter(
    (item) => item.flowId === flowId,
  ).length;
  if (flowVersionCount > 1) {
    return undefined;
  }

  return toolNameByFlow.get(flowId)?.trim();
}

function getInitialToolNameForReview(
  initialToolNameByFlow: Map<string, string>,
  attachmentKey: string,
  flowId: string,
  items: ReviewFlowItem[],
) {
  const strictValue = initialToolNameByFlow.get(attachmentKey);
  if (strictValue !== undefined) {
    return strictValue;
  }

  const flowVersionCount = items.filter(
    (item) => item.flowId === flowId,
  ).length;
  if (flowVersionCount > 1) {
    return undefined;
  }

  return initialToolNameByFlow.get(flowId);
}

interface BuildReviewFlowsParams {
  allFlows: Array<{ id: string; name: string }>;
  attachedConnectionByFlow: Map<string, string[]>;
  connections: ConnectionItem[];
  defaultToolNameScopeId: string | null;
  selectedVersionByFlow: Map<
    string,
    {
      flowId?: string;
      flowName?: string;
      versionId: string;
      versionTag: string;
    }
  >;
  toolNameByFlow: Map<string, string>;
}

export function buildReviewFlows({
  allFlows,
  attachedConnectionByFlow,
  connections,
  defaultToolNameScopeId,
  selectedVersionByFlow,
  toolNameByFlow,
}: BuildReviewFlowsParams): ReviewFlowItem[] {
  const selectedItems = Array.from(selectedVersionByFlow.entries()).map(
    ([attachmentKey, entry]) => ({
      attachmentKey,
      flowId: entry.flowId ?? attachmentKey,
    }),
  );

  return Array.from(selectedVersionByFlow.entries()).map(
    ([attachmentKey, entry]) => {
      const flowId = entry.flowId ?? attachmentKey;
      const flow = allFlows.find((item) => item.id === flowId);
      const connectionIds =
        attachedConnectionByFlow.get(attachmentKey) ??
        attachedConnectionByFlow.get(flowId) ??
        [];
      const flowConnections = connectionIds
        .map((connectionId) =>
          connections.find((connection) => connection.id === connectionId),
        )
        .filter(
          (connection): connection is ConnectionItem => connection != null,
        );

      const connectionDetails = flowConnections.map((connection) => {
        const envVars = connection.environmentVariables
          ? Object.keys(connection.environmentVariables).map((key) => ({
              key,
              masked: "••••••••",
            }))
          : [];

        return {
          name: connection.name,
          isNew: connection.isNew ?? false,
          envVars,
        };
      });

      const flowName = flow?.name ?? entry.flowName ?? "Unknown";
      const defaultToolName = getDefaultDeploymentToolName(
        flowName,
        entry.versionId,
        defaultToolNameScopeId,
      );

      return {
        attachmentKey,
        flowId,
        flowName,
        toolName:
          getToolNameForReview(
            toolNameByFlow,
            attachmentKey,
            flowId,
            selectedItems,
          ) || defaultToolName,
        defaultToolName,
        versionLabel: entry.versionTag || entry.versionId,
        connectionDetails,
      };
    },
  );
}

interface BuildToolNamesToCheckParams {
  initialToolNameByFlow: Map<string, string>;
  isEditMode: boolean;
  preExistingFlowIds: Set<string>;
  reviewFlows: ReviewFlowItem[];
}

export function buildToolNamesToCheck({
  initialToolNameByFlow,
  isEditMode,
  preExistingFlowIds,
  reviewFlows,
}: BuildToolNamesToCheckParams): string[] {
  const names: string[] = [];

  for (const item of reviewFlows) {
    const normalized = normalizeWxoName(item.toolName);
    if (!normalized) continue;

    if (isEditMode && preExistingFlowIds.has(item.attachmentKey)) {
      const original = normalizeWxoName(
        getInitialToolNameForReview(
          initialToolNameByFlow,
          item.attachmentKey,
          item.flowId,
          reviewFlows,
        ) ?? "",
      );

      if (
        normalized.toLowerCase() === original.toLowerCase() ||
        normalized.toLowerCase() ===
          normalizeWxoName(item.defaultToolName).toLowerCase()
      ) {
        continue;
      }
    }

    names.push(normalized);
  }

  return names;
}

interface BuildToolNameErrorsParams {
  existingToolNames: Set<string>;
  initialToolNameByFlow: Map<string, string>;
  isEditMode: boolean;
  preExistingFlowIds: Set<string>;
  reviewFlows: ReviewFlowItem[];
}

export function buildToolNameErrors({
  existingToolNames,
  initialToolNameByFlow,
  isEditMode,
  preExistingFlowIds,
  reviewFlows,
}: BuildToolNameErrorsParams) {
  const errors = new Map<string, string>();
  const batchNames = new Map<string, string>();

  for (const item of reviewFlows) {
    const normalized = normalizeWxoName(item.toolName).toLowerCase();
    if (!normalized) continue;

    const firstAttachmentKey = batchNames.get(normalized);
    if (firstAttachmentKey) {
      errors.set(
        item.attachmentKey,
        "Duplicate tool name within this deployment",
      );
      if (!errors.has(firstAttachmentKey)) {
        errors.set(
          firstAttachmentKey,
          "Duplicate tool name within this deployment",
        );
      }
    } else {
      batchNames.set(normalized, item.attachmentKey);
    }

    if (!errors.has(item.attachmentKey) && existingToolNames.has(normalized)) {
      let skipProviderCheck = false;

      if (isEditMode && preExistingFlowIds.has(item.attachmentKey)) {
        const original = normalizeWxoName(
          getInitialToolNameForReview(
            initialToolNameByFlow,
            item.attachmentKey,
            item.flowId,
            reviewFlows,
          ) ?? "",
        ).toLowerCase();

        skipProviderCheck =
          normalized === original ||
          normalized === normalizeWxoName(item.defaultToolName).toLowerCase();
      }

      if (!skipProviderCheck) {
        errors.set(
          item.attachmentKey,
          "Edit tool name (already exists in provider)",
        );
      }
    }
  }

  return errors;
}
