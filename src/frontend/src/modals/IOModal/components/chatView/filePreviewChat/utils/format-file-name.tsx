export default function formatFileName(name: string): string {
  const fileExtension = name.split(".").pop(); // Get the file extension
  const baseName = name.slice(0, name.lastIndexOf(".")); // Get the base name without the extension
  if (baseName.length > 6) {
    return `${baseName.slice(0, 29)}...${fileExtension}`;
  }
  return name;
}
