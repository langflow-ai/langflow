import { cloneDeep } from "lodash";
import type { APIClassType } from "@/types/api";

export type CloudFieldOverride = {
  value?: unknown;
  placeholder?: string;
};

export type CloudUiMetadata = Record<string, unknown> & {
  cloud_default_overrides?: Record<string, CloudFieldOverride>;
  cloud_incompatible_options?: Record<string, unknown[]>;
};

function isCloudUiMetadata(value: unknown): value is CloudUiMetadata {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

export function getCloudUiMetadata(
  value: unknown,
): CloudUiMetadata | undefined {
  return isCloudUiMetadata(value) ? value : undefined;
}

export function getCloudOptionName(option: unknown): unknown {
  if (typeof option === "object" && option !== null && "name" in option) {
    return (option as { name?: unknown }).name ?? option;
  }

  return option;
}

export function isCloudIncompatibleOption(
  option: unknown,
  incompatibleOptions: readonly unknown[] = [],
): boolean {
  return incompatibleOptions.some(
    (incompatibleOption) => incompatibleOption === getCloudOptionName(option),
  );
}

export function filterCloudCompatibleOptions<T>(
  options: T[] | undefined,
  incompatibleOptions: readonly unknown[] = [],
): T[] | undefined {
  if (!options || incompatibleOptions.length === 0) {
    return options;
  }

  return options.filter(
    (option) => !isCloudIncompatibleOption(option, incompatibleOptions),
  );
}

export function getCloudFieldOverride(
  metadata: CloudUiMetadata | undefined,
  fieldName: string,
): CloudFieldOverride | undefined {
  return metadata?.cloud_default_overrides?.[fieldName];
}

export function getCloudIncompatibleOptions(
  metadata: CloudUiMetadata | undefined,
  fieldName: string,
): unknown[] {
  const incompatibleOptions = metadata?.cloud_incompatible_options?.[fieldName];
  return Array.isArray(incompatibleOptions) ? incompatibleOptions : [];
}

export function applyCloudDefaultOverrides(
  component: APIClassType,
  cloudDefaultOverrides?: Record<string, CloudFieldOverride>,
): void {
  if (!cloudDefaultOverrides) {
    return;
  }

  Object.entries(cloudDefaultOverrides).forEach(([fieldName, override]) => {
    if (!component.template?.[fieldName]) {
      return;
    }

    if (Object.hasOwn(override, "value")) {
      component.template[fieldName].value = override.value;
    }

    if (override.placeholder !== undefined) {
      component.template[fieldName].placeholder = override.placeholder;
    }
  });
}

export function sanitizeCloudIncompatibleDefaults(
  component: APIClassType,
  cloudIncompatibleOptions?: Record<string, unknown[]>,
): void {
  if (!cloudIncompatibleOptions) {
    return;
  }

  Object.entries(cloudIncompatibleOptions).forEach(
    ([fieldName, incompatibleOptions]) => {
      if (!Array.isArray(incompatibleOptions)) {
        return;
      }

      const templateField = component.template?.[fieldName];
      if (!templateField) {
        return;
      }

      const selectedOptions = Array.isArray(templateField.value)
        ? templateField.value
        : templateField.value
          ? [templateField.value]
          : [];

      const filteredSelections = selectedOptions.filter(
        (selection) =>
          !isCloudIncompatibleOption(selection, incompatibleOptions),
      );

      if (filteredSelections.length > 0) {
        templateField.value = filteredSelections;
        return;
      }

      if (templateField.limit !== 1 || !Array.isArray(templateField.options)) {
        templateField.value = filteredSelections;
        return;
      }

      const compatibleOptions = filterCloudCompatibleOptions(
        templateField.options,
        incompatibleOptions,
      );
      const firstCompatibleOption = compatibleOptions?.[0];

      templateField.value = firstCompatibleOption
        ? [cloneDeep(firstCompatibleOption)]
        : [];
    },
  );
}

export function withCurrentCloudMetadata(
  savedNode: APIClassType | undefined,
  currentCatalogNode: APIClassType | undefined,
): APIClassType | undefined {
  if (!savedNode || !currentCatalogNode) {
    return savedNode;
  }

  const savedMetadata = getCloudUiMetadata(savedNode.metadata);
  const currentMetadata = getCloudUiMetadata(currentCatalogNode.metadata);

  const shouldOverlayCloudCompatible =
    savedNode.cloud_compatible === undefined &&
    currentCatalogNode.cloud_compatible !== undefined;
  const shouldOverlayCloudDefaultOverrides =
    savedMetadata?.cloud_default_overrides === undefined &&
    currentMetadata?.cloud_default_overrides !== undefined;
  const shouldOverlayCloudIncompatibleOptions =
    savedMetadata?.cloud_incompatible_options === undefined &&
    currentMetadata?.cloud_incompatible_options !== undefined;

  if (
    !shouldOverlayCloudCompatible &&
    !shouldOverlayCloudDefaultOverrides &&
    !shouldOverlayCloudIncompatibleOptions
  ) {
    return savedNode;
  }

  const nextMetadata =
    shouldOverlayCloudDefaultOverrides || shouldOverlayCloudIncompatibleOptions
      ? {
          ...((savedMetadata ?? {}) as Record<string, unknown>),
          ...(shouldOverlayCloudDefaultOverrides
            ? {
                cloud_default_overrides:
                  currentMetadata?.cloud_default_overrides,
              }
            : {}),
          ...(shouldOverlayCloudIncompatibleOptions
            ? {
                cloud_incompatible_options:
                  currentMetadata?.cloud_incompatible_options,
              }
            : {}),
        }
      : savedMetadata;

  return {
    ...savedNode,
    ...(shouldOverlayCloudCompatible
      ? {
          cloud_compatible: currentCatalogNode.cloud_compatible,
        }
      : {}),
    ...(nextMetadata !== undefined
      ? {
          metadata: nextMetadata,
        }
      : {}),
  } as APIClassType;
}
