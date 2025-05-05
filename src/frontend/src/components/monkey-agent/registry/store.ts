/**
 * Store for the enhanced registry
 */
import { create } from "zustand";
import { getEnhancedRegistry, getTypeCompatibilityMatrix } from "./client";
import { EnhancedRegistry } from "./types";

interface EnhancedRegistryState {
  registry: EnhancedRegistry;
  typeCompatibility: Record<string, string[]>;
  isLoaded: boolean;
  error: string | null;

  fetchRegistry: () => Promise<void>;
  getNodeById: (nodeId: string) => any | null;
  areTypesCompatible: (sourceType: string, targetType: string) => boolean;
  findCompatibleInputs: (sourceType: string) => string[];
  findCompatibleOutputs: (targetType: string) => string[];
}

export const useEnhancedRegistryStore = create<EnhancedRegistryState>(
  (set, get) => ({
    registry: {},
    typeCompatibility: {},
    isLoaded: false,
    error: null,

    fetchRegistry: async () => {
      try {
        const [registry, typeCompatibility] = await Promise.all([
          getEnhancedRegistry(),
          getTypeCompatibilityMatrix(),
        ]);

        set({
          registry,
          typeCompatibility,
          isLoaded: true,
          error: null,
        });
      } catch (error) {
        console.error("Error fetching enhanced registry:", error);
        set({
          error:
            error instanceof Error
              ? error.message
              : "Unknown error fetching registry",
          isLoaded: false,
        });
      }
    },

    getNodeById: (nodeId: string) => {
      const { registry } = get();
      return registry[nodeId] || null;
    },

    areTypesCompatible: (sourceType: string, targetType: string) => {
      const { typeCompatibility } = get();
      if (!typeCompatibility[sourceType]) return false;
      return typeCompatibility[sourceType].includes(targetType);
    },

    findCompatibleInputs: (sourceType: string) => {
      const { typeCompatibility } = get();
      return typeCompatibility[sourceType] || [];
    },

    findCompatibleOutputs: (targetType: string) => {
      const { typeCompatibility } = get();
      // Find all source types that can connect to this target type
      return Object.entries(typeCompatibility)
        .filter(([_, compatibleTypes]) => compatibleTypes.includes(targetType))
        .map(([sourceType, _]) => sourceType);
    },
  }),
);
