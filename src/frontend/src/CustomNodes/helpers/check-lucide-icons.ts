import dynamicIconImports from "lucide-react/dynamicIconImports";
import { categoryIcons } from "@/utils/styleUtils";

export const checkLucideIcons = (iconName: string): boolean => {
  return !!dynamicIconImports[iconName] || !!categoryIcons[iconName];
};
