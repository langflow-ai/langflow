export function appendErrorSuggestion(
  detail: string | undefined,
  suggestion: string,
): string {
  if (!detail) return suggestion;
  if (detail.includes(suggestion)) return detail;

  const trimmedDetail = detail.trim();
  const separator = /[.!?]$/.test(trimmedDetail) ? " " : ". ";
  return `${trimmedDetail}${separator}${suggestion}`;
}

export function getRequiredFieldError(
  shouldValidate: boolean,
  value: string,
  message: string,
): string | undefined {
  return shouldValidate && value.trim() === "" ? message : undefined;
}
