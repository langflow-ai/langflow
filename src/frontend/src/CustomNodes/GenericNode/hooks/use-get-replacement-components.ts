import { ENABLE_INTEGRATIONS } from "@/customization/feature-flags";
import { useTypesStore } from "@/stores/typesStore";
import { requiresConnectionRef } from "@/utils/connection-ref-gate";

export const useGetReplacementComponents = (replacement?: string[]) => {
  const data = useTypesStore((state) => state.data);

  return replacement && Array.isArray(replacement) && replacement.length > 0
    ? replacement.map((component) => {
        const categoryName = component?.split(".")[0];
        const componentName = component?.split(".")[1];
        const replacementComponent =
          categoryName && componentName
            ? data[categoryName]?.[componentName]
            : undefined;

        // The palette hides connection-backed components while
        // ENABLE_INTEGRATIONS is OFF, so the hint must not point at them.
        if (
          !ENABLE_INTEGRATIONS &&
          requiresConnectionRef(replacementComponent)
        ) {
          return undefined;
        }

        return replacementComponent?.display_name;
      })
    : [];
};
