import type { ModelProviderWithStatus } from "@/controllers/API/queries/models/use-get-model-providers";
import type { ModelOption, SelectedModel } from "../types";
import { matchesModelIdentity } from "./model-option-identity";
import { recoverModelOption } from "./recover-model-option";

export interface DeriveSelectedModelParams {
  isConnectionMode: boolean;
  /** Resolved `t("modelInput.connectOtherModels")` label. */
  connectLabel: string;
  /** External node icon; falls back to "CornerDownLeft". */
  connectIcon: string | undefined;
  savedValue: ModelOption | undefined;
  flatOptions: ModelOption[];
  providers: ModelProviderWithStatus[] | undefined;
  /**
   * Whether `providers` reflects settled server state (not fetching, no error).
   * While it is false the saved provider's `is_configured` is not read at all;
   * the status stays unknown and the saved value renders through the
   * not-enabled-locally trigger.
   */
  providerStatusIsReliable: boolean;
  /** Current value of the component's `hasProcessedEmptyRef` (read-only here). */
  hasProcessedEmpty: boolean;
}

/**
 * Derives the currently selected model shown in the trigger. Pure: extracted
 * verbatim from ModelInputComponent's `selectedModel` memo (LE-1736 W23). Shares
 * `hasProcessedEmpty` with useAutoSelectModel (W24), passed in by value.
 */
export function deriveSelectedModel({
  isConnectionMode,
  connectLabel,
  connectIcon,
  savedValue,
  flatOptions,
  providers,
  providerStatusIsReliable,
  hasProcessedEmpty,
}: DeriveSelectedModelParams): SelectedModel | null {
  if (isConnectionMode) {
    return {
      name: connectLabel,
      icon: connectIcon || "CornerDownLeft",
      provider: "",
    } as SelectedModel;
  }

  const saved = recoverModelOption(savedValue);
  const currentName = saved?.name;
  if (!currentName) {
    if (flatOptions.length > 0 && !hasProcessedEmpty) {
      return flatOptions[0];
    }
    return null;
  }

  const match = flatOptions.find((option) =>
    matchesModelIdentity(option, saved),
  );
  if (match) return match;

  if (saved) {
    const savedProviderConfigured = providerStatusIsReliable
      ? providers?.some((p) => p.provider === saved.provider && p.is_configured)
      : undefined;
    if (!savedProviderConfigured) {
      return {
        ...(saved.id && { id: saved.id }),
        name: saved.name,
        icon: saved.icon || "Bot",
        provider: saved.provider || "Unknown",
        metadata: {
          ...(saved.metadata ?? {}),
          not_enabled_locally: true,
        },
      } as SelectedModel;
    }
  }

  return flatOptions.length > 0 ? flatOptions[0] : null;
}
