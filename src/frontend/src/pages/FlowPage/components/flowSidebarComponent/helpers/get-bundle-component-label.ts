/** Shorten a component label only when it repeats its enclosing bundle name. */
export function getBundleComponentLabel(
  bundleName: string,
  componentName: string,
): string {
  if (!componentName.toLowerCase().startsWith(bundleName.toLowerCase())) {
    return componentName;
  }

  const suffix = componentName.slice(bundleName.length);
  const label = suffix.startsWith(":")
    ? suffix.slice(1).trimStart()
    : suffix.trimStart();
  return suffix.startsWith(":") || suffix.startsWith(" ")
    ? label || componentName
    : componentName;
}
