export function convertTestName(name: string): string {
  return name.replace(/ /g, "-").toLowerCase();
}
