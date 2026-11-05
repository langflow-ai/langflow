import { getAxiosErrorDetail } from "@/controllers/API/helpers/get-axios-error-message";
import type {
  TriggerRead,
  TriggerStateReason,
} from "@/controllers/API/queries/triggers";

/** The `t` of `useTranslation()`, narrowed to what these helpers call. */
type Translate = (key: string) => string;

/**
 * Codes the server gives the trigger errors it words in English
 * (`services/triggers/error_codes.py`). Each one has a translated message, so
 * the reader sees it in their language; an error without a known code is
 * shown as the server wrote it.
 */
export const TRIGGER_ERROR_CODES = [
  "multiple_triggers",
  "node_removed",
  "source_settings_changed",
  "connection_not_authorized",
  "invalid_cron",
  "cron_never_matches",
  "timezone_required",
  "unknown_timezone",
  "background_runs_not_allowed",
  "connection_unusable",
] as const;
export type TriggerErrorCode = (typeof TRIGGER_ERROR_CODES)[number];

const KNOWN_CODES: ReadonlySet<string> = new Set(TRIGGER_ERROR_CODES);

export const isTriggerErrorCode = (code: unknown): code is TriggerErrorCode =>
  typeof code === "string" && KNOWN_CODES.has(code);

/** The state reason that already says what the stored error says. */
const STATED_BY_REASON: Partial<Record<TriggerErrorCode, TriggerStateReason>> =
  {
    node_removed: "node_removed",
    source_settings_changed: "source_settings_changed",
    connection_not_authorized: "consent_required",
  };

/**
 * The stored error to show under a trigger's reason, in the reader's language,
 * or `null` when there is none or the reason already says it.
 */
export function lastErrorText(
  trigger: Pick<TriggerRead, "last_error" | "last_error_code" | "reason">,
  t: Translate,
): string | null {
  const { last_error: text, last_error_code: code } = trigger;
  if (!text || trigger.reason === "ready_to_resume") return null;
  if (!isTriggerErrorCode(code)) return text;
  if (STATED_BY_REASON[code] === trigger.reason) return null;
  return t(`triggers.serverError.${code}`);
}

const refusalCodeOf = (error: unknown): unknown =>
  (error as { response?: { data?: { detail?: { code?: unknown } } } } | null)
    ?.response?.data?.detail?.code;

/** Why the server refused a trigger action, in the reader's language when it can be. */
export function triggerRefusalText(error: unknown, t: Translate): string {
  const code = refusalCodeOf(error);
  return isTriggerErrorCode(code)
    ? t(`triggers.serverError.${code}`)
    : getAxiosErrorDetail(error, t("triggers.errors.unknown"));
}
