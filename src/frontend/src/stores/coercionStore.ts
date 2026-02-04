import { create } from "zustand";

/**
 * Types that are interchangeable when auto-coercion is enabled.
 * Only these three types can be coerced to each other.
 * All other types (LanguageModel, Tool, Embeddings, etc.) remain strictly typed.
 */
export const COERCIBLE_TYPES = ["Data", "Message", "DataFrame"];

type CoercionSettings = {
  enabled: boolean;
  autoParse: boolean; // Detect and convert JSON/CSV strings (mirrors Type Convert component)
};

type CoercionStoreType = {
  coercionSettings: CoercionSettings;
  setCoercionEnabled: (value: boolean) => void;
  setAutoParse: (value: boolean) => void;
  isCoercibleType: (type: string) => boolean;
  areTypesCoercible: (sourceTypes: string[], targetTypes: string[]) => boolean;
};

const DEFAULT_SETTINGS: CoercionSettings = {
  enabled: false,
  autoParse: false,
};

const STORAGE_KEY = "coercionSettings";

const loadSettings = (): CoercionSettings => {
  try {
    const stored = window.localStorage.getItem(STORAGE_KEY);
    if (stored) {
      const parsed = JSON.parse(stored);
      // Validate the parsed object has the expected shape
      if (
        typeof parsed.enabled === "boolean" &&
        typeof parsed.autoParse === "boolean"
      ) {
        return parsed;
      }
    }
  } catch (e) {
    console.warn("Failed to load coercion settings from localStorage:", e);
  }
  return DEFAULT_SETTINGS;
};

const saveSettings = (settings: CoercionSettings) => {
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(settings));
  } catch (e) {
    console.warn("Failed to save coercion settings to localStorage:", e);
  }
};

export const useCoercionStore = create<CoercionStoreType>((set, get) => ({
  coercionSettings: loadSettings(),

  setCoercionEnabled: (value: boolean) => {
    const newSettings = { ...get().coercionSettings, enabled: value };
    saveSettings(newSettings);
    set({ coercionSettings: newSettings });
  },

  setAutoParse: (value: boolean) => {
    const newSettings = { ...get().coercionSettings, autoParse: value };
    saveSettings(newSettings);
    set({ coercionSettings: newSettings });
  },

  /**
   * Check if a single type is coercible (Data, Message, or DataFrame)
   */
  isCoercibleType: (type: string): boolean => {
    return COERCIBLE_TYPES.includes(type);
  },

  /**
   * Check if two sets of types can be coerced to each other.
   * Returns true only if auto-coercion is enabled AND both have at least one coercible type.
   */
  areTypesCoercible: (
    sourceTypes: string[],
    targetTypes: string[],
  ): boolean => {
    const { coercionSettings } = get();
    if (!coercionSettings.enabled) {
      return false;
    }

    const sourceHasCoercible = sourceTypes.some((t) =>
      COERCIBLE_TYPES.includes(t),
    );
    const targetHasCoercible = targetTypes.some((t) =>
      COERCIBLE_TYPES.includes(t),
    );

    return sourceHasCoercible && targetHasCoercible;
  },
}));

export default useCoercionStore;
