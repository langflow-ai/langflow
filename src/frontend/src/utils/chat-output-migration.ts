// ChatOutput changed its input widget from MessageInput/str to HandleInput/other while
// retaining string and message support. This is deliberately not a general str/other alias.
// Must match lfx.template.field_migrations.can_migrate_chat_output_input.
export const canMigrateChatOutputInput = (
  component: unknown,
  fieldName: string,
  currentField: { type?: string; _input_type?: string } | undefined,
  savedField: { type?: string; value?: unknown },
): boolean => {
  const metadata =
    component && typeof component === "object" && "metadata" in component
      ? component.metadata
      : undefined;
  return (
    metadata !== null &&
    typeof metadata === "object" &&
    "component_class_name" in metadata &&
    metadata.component_class_name === "ChatOutput" &&
    fieldName === "input_value" &&
    savedField.type === "str" &&
    currentField?.type === "other" &&
    currentField._input_type === "HandleInput" &&
    (savedField.value == null || typeof savedField.value === "string")
  );
};
