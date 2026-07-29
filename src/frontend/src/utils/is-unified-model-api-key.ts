import type { APIClassType } from "@/types/api";

export function isUnifiedModelApiKeyField(
  node: APIClassType | undefined,
  fieldName: string | undefined,
): boolean {
  const apiKeyField = fieldName ? node?.template?.[fieldName] : undefined;
  const modelField = node?.template?.model;

  return (
    fieldName === "api_key" &&
    apiKeyField?.display_name === "API Key" &&
    (modelField?._input_type === "ModelInput" || modelField?.type === "model")
  );
}
