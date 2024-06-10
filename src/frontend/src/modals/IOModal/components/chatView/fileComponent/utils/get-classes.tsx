export default function getClasses(isHovered: boolean): string {
  return `relative ${
    false ? "h-20 w-20" : "h-20 w-80"
  } cursor-pointer rounded-lg border  border-ring bg-muted shadow transition duration-300 hover:drop-shadow-lg ${
    isHovered ? "shadow-md" : ""
  }`;
}
