export default function sortByName(stringList: string[]): string[] {
  return stringList.sort((a, b) => a.localeCompare(b));
}
