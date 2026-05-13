import type { SelectedFlowVersion } from "../types";
import { getSelectedFlowVersionKey } from "../types";

export function normalizeSelectedFlowVersions(
  versions?: Map<string, SelectedFlowVersion>,
): Map<string, SelectedFlowVersion> {
  const next = new Map<string, SelectedFlowVersion>();
  for (const [key, value] of versions ?? new Map()) {
    const flowId = value.flowId ?? key;
    const versionId = value.versionId;
    const normalizedKey = value.flowId
      ? getSelectedFlowVersionKey(flowId, versionId)
      : key;
    next.set(normalizedKey, {
      key: normalizedKey,
      flowId,
      flowName: value.flowName,
      versionId,
      versionTag: value.versionTag,
    });
  }
  return next;
}

export function getValueByAttachmentKeyOrFlowId<T>(
  map: Map<string, T>,
  attachmentKey: string,
  flowId: string,
): T | undefined {
  return map.get(attachmentKey) ?? map.get(flowId);
}

export function getScopedValueForUniqueFlowVersion<T>(
  map: Map<string, T>,
  attachmentKey: string,
  flowId: string,
  flowVersionCount: number,
): T | undefined {
  const strictValue = map.get(attachmentKey);
  if (strictValue !== undefined) {
    return strictValue;
  }

  if (flowVersionCount > 1) {
    return undefined;
  }

  return map.get(flowId);
}

export function getFlowVersionCount(
  entries: Iterable<{ flowId?: string }>,
  flowId: string,
) {
  return Array.from(entries).filter((entry) => entry.flowId === flowId).length;
}
