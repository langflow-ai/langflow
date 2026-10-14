/**
 * The palette label for a component shown under its bundle's heading.
 *
 * Only the `Bundle: Component` form is shortened ("Slack: On Message" under
 * "Slack" reads "On Message"): there the prefix is only the bundle's name. A
 * name that merely starts with the bundle's name keeps it, because there the
 * name is the product - "OpenAI Embeddings" must not read "Embeddings", and
 * "Exa Search" and "DuckDuckGo Search" must not both read "Search".
 */
export function getBundleComponentLabel(
  bundleName: string,
  componentName: string,
): string {
  const prefix = `${bundleName}:`;
  if (!componentName.toLowerCase().startsWith(prefix.toLowerCase())) {
    return componentName;
  }
  return componentName.slice(prefix.length).trim() || componentName;
}
