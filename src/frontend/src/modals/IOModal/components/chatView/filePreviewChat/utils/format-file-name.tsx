export default function formatFileName(
  name: string,
  numberToTruncate: number = 25,
): string {
  if (name[numberToTruncate] === undefined) {
    return name;
  }
  const fileExtension = name.split(".").pop(); // Get the file extension
  const baseName = name.slice(0, name.lastIndexOf(".")); // Get the base name without the extension
  if (baseName.length > 6) {
    return `${baseName.slice(0, numberToTruncate)}...${fileExtension}`;
  }
  return name;
}
