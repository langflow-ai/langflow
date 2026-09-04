/**
 * Attribute bundle that opts a field out of browser + password-manager autofill.
 *
 * Langflow component-configuration fields are not login/web forms, yet browsers
 * (notably Chrome) and password managers heuristically classify them as
 * credential fields and inject saved values into them. Because Langflow
 * autosaves, an injected value silently overwrites the real one and persists it,
 * corrupting the flow.
 *
 * `autocomplete="off"` alone is NOT honored by Chrome for credential-like fields
 * (a deliberate behavior since 2014), so suppression additionally:
 *   - marks secret/password fields as `new-password` — the browser-endorsed
 *     token that suppresses saved-credential injection AND removes the field
 *     from the username/password pairing heuristic that fills adjacent text
 *     fields (e.g. the component name) with a saved username; and
 *   - emits the data-* opt-outs understood by 1Password / LastPass / Bitwarden /
 *     Dashlane.
 *
 * These are non-standard data attributes, so they are spread as raw DOM props.
 */
export const PASSWORD_MANAGER_IGNORE_PROPS = {
  "data-1p-ignore": "true",
  "data-lpignore": "true",
  "data-bwignore": "true",
  "data-form-type": "other",
} as const;

/**
 * Resolves the `autocomplete` value for an autofill-suppressed input.
 *
 * Keyed on the field's intrinsic secret-ness, NOT its live `type`, so toggling
 * password visibility (password <-> text) does not re-arm autofill.
 *
 * @param isPassword whether the field holds a secret (API key, token, password).
 */
export function getSuppressedAutoComplete(isPassword: boolean): string {
  return isPassword ? "new-password" : "off";
}

/**
 * Stamps the autofill-suppression attributes onto a raw input/textarea element.
 *
 * For inputs that React props cannot reach — e.g. ag-grid cell editors, which
 * render their own `<input>`/`<textarea>` outside React when a cell enters edit
 * mode. Idempotent; safe to call on every editing-started event.
 */
export function suppressAutofillOnElement(
  element: HTMLInputElement | HTMLTextAreaElement | null | undefined,
): void {
  if (!element) return;
  element.setAttribute("autocomplete", "off");
  for (const [key, value] of Object.entries(PASSWORD_MANAGER_IGNORE_PROPS)) {
    element.setAttribute(key, value);
  }
}
