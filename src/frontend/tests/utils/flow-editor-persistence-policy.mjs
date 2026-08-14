function isRecord(value) {
  return typeof value === "object" && value !== null;
}

export function isModelRefreshBody(value) {
  if (!isRecord(value) || typeof value.field !== "string") return false;
  const template = value.template;
  if (!isRecord(template)) return false;
  const modelField = template[value.field];
  return isRecord(modelField) && modelField.type === "model";
}

export function isMatchingFullFlowAutosavePayload(value, matchesData) {
  if (!isRecord(value) || !isRecord(value.data)) return false;

  const hasFlowMetadata = [
    "description",
    "endpoint_name",
    "folder_id",
    "locked",
    "name",
  ].every((key) => key in value);
  return hasFlowMetadata && matchesData(value.data);
}

export function canTrackFullFlowAutosavePayload(
  value,
  matchesData,
  observedModelRefreshes,
  expectedModelRefreshes,
) {
  return (
    observedModelRefreshes >= expectedModelRefreshes &&
    isMatchingFullFlowAutosavePayload(value, matchesData)
  );
}

export function isFlowPersistenceBarrierSatisfied(
  autosaveFinished,
  completedModelRefreshes,
  requiredModelRefreshes,
) {
  return autosaveFinished && completedModelRefreshes >= requiredModelRefreshes;
}

export function modelRefreshNodeCount(data) {
  return (data.nodes ?? []).filter((node) => {
    if (node.type !== "genericNode") return false;
    const template = node.data?.node?.template;
    return (
      template !== undefined &&
      Object.values(template).some(
        (field) => isRecord(field) && field.type === "model",
      )
    );
  }).length;
}

export function requiresPostRefreshAutosave(data) {
  return modelRefreshNodeCount(data) > 0;
}
