// The login API answers in English with no error code. These are the details
// it sends for a failed sign-in, mapped to copy in the interface language.
export const LOGIN_ERROR_KEYS: Readonly<Record<string, string>> = {
  "Incorrect username or password": "errors.signinInvalidCredentials", // pragma: allowlist secret
  "An error occurred during authentication": "errors.signinUnexpected",
};

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
