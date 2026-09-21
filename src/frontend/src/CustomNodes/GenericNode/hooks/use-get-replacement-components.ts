import { ENABLE_INTEGRATIONS } from "@/customization/feature-flags";
import { useTypesStore } from "@/stores/typesStore";
import { requiresConnectionRef } from "@/utils/connection-ref-gate";
import { resolvePaletteKey } from "../../utils/resolve-palette-key";

export type ReplacementComponent = {
  displayName: string;
  // ``<category>.<palette key>`` for ``setFilterComponent``. The palette key
  // is the ``ext:`` identifier for extension-bundle components, so it can
  // differ from the class name in the ``replacement`` reference.
  filterKey: string;
};

export const useGetReplacementComponents = (
  replacement?: string[],
): (ReplacementComponent | undefined)[] => {
  const data = useTypesStore((state) => state.data);

  return replacement && Array.isArray(replacement) && replacement.length > 0
    ? replacement.map((component) => {
        const categoryName = component?.split(".")[0];
        const componentName = component?.split(".")[1];
        const paletteKey =
          categoryName && componentName
            ? resolvePaletteKey(data, categoryName, componentName)
            : undefined;
        const replacementComponent = paletteKey
          ? data[categoryName][paletteKey]
          : undefined;

        // The palette hides connection-backed components while
        // ENABLE_INTEGRATIONS is OFF, so the hint must not point at them.
        if (
          !replacementComponent?.display_name ||
          (!ENABLE_INTEGRATIONS && requiresConnectionRef(replacementComponent))
        ) {
          return undefined;
        }

        return {
          displayName: replacementComponent.display_name,
          filterKey: `${categoryName}.${paletteKey}`,
        };
      })
    : [];
};
