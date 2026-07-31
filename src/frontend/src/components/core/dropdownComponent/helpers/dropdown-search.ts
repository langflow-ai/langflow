/** Strips presentation-only keys from an option's metadata entry. */
export const filterMetadataKeys = (
  // biome-ignore lint/suspicious/noExplicitAny: legacy
  metadata: Record<string, any> = {},
  excludeKeys: string[] = [
    "api_endpoint",
    "icon",
    "status",
    "org_id",
    "id",
    "updated_at",
  ],
) => {
  return Object.fromEntries(
    Object.entries(metadata).filter(([key]) => !excludeKeys.includes(key)),
  );
};

/** Builds the multi-line tooltip for an option from its metadata entry. */
export const formatTooltipContent = (
  option: string,
  index: number,
  // biome-ignore lint/suspicious/noExplicitAny: legacy
  filteredMetadata: Record<string, any>[] | undefined,
  firstWord: string,
) => {
  if (!filteredMetadata?.[index]) return option;

  const metadata = filteredMetadata[index];
  const metadataEntries = Object.entries(metadata)
    .filter(
      ([key, value]) =>
        value !== null &&
        key !== "icon" &&
        key !== "id" &&
        key !== "updated_at",
    )
    .map(([key, value]) => {
      const displayValue =
        typeof value === "string" && value.length > 20
          ? `${value.substring(0, 30)}...`
          : String(value);
      return `${key}: ${displayValue}`;
    });

  return metadataEntries.length > 0
    ? `${firstWord}: ${option}\n${metadataEntries.join("\n")}`
    : option;
};
