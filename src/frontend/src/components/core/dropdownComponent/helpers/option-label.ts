/** Labels for options, keyed by the option value the field saves. */
export type OptionLabels = Record<string, string> | undefined;

/** The text to show for `option`: its translated label, or the option itself. */
export const optionLabel = (labels: OptionLabels, option: string): string =>
  labels?.[option] ?? option;

/** Options paired with their labels, so a search matches what the reader sees. */
export const searchableOptions = (
  options: string[],
  labels: OptionLabels,
): { value: string; label: string }[] =>
  options.map((value) => ({ value, label: optionLabel(labels, value) }));
