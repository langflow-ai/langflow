import {
  getFlowVersionCount,
  getScopedValueForUniqueFlowVersion,
} from "../../helpers/version-scope";
import type { ConnectionItem } from "../../types";
import { getDefaultDeploymentToolName, UNKNOWN_FLOW_NAME } from "../../types";
import type { ReviewFlowItem } from "./types";

function getToolNameForReview(
  toolNameByFlow: Map<string, string>,
  attachmentKey: string,
  flowId: string,
  items: Array<{ attachmentKey: string; flowId: string }>,
) {
  return getScopedValueForUniqueFlowVersion(
    toolNameByFlow,
    attachmentKey,
    flowId,
    getFlowVersionCount(items, flowId),
  )?.trim();
}

interface BuildReviewFlowsParams {
  allFlows: Array<{ id: string; name: string }>;
  attachedConnectionByFlow: Map<string, string[]>;
  connections: ConnectionItem[];
  removedFlowIds: Set<string>;
  selectedVersionByFlow: Map<
    string,
    {
      key?: string;
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
  removedFlowIds,
  selectedVersionByFlow,
  toolNameByFlow,
}: BuildReviewFlowsParams): ReviewFlowItem[] {
  const selectedItems = Array.from(selectedVersionByFlow.entries()).map(
    ([attachmentKey, entry]) => ({
      attachmentKey: entry.key ?? attachmentKey,
      flowId: entry.flowId ?? attachmentKey,
    }),
  );

  return Array.from(selectedVersionByFlow.entries())
    .map(([attachmentKey, entry]) => {
      const normalizedAttachmentKey = entry.key ?? attachmentKey;
      if (removedFlowIds.has(normalizedAttachmentKey)) {
        return null;
      }
      const flowId = entry.flowId ?? attachmentKey;
      const flow = allFlows.find((item) => item.id === flowId);
      const connectionIds =
        attachedConnectionByFlow.get(normalizedAttachmentKey) ??
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

      const flowName = flow?.name ?? entry.flowName ?? UNKNOWN_FLOW_NAME;
      const defaultToolName = getDefaultDeploymentToolName(flowName);

      return {
        attachmentKey: normalizedAttachmentKey,
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
    })
    .filter((item): item is ReviewFlowItem => item !== null);
}
